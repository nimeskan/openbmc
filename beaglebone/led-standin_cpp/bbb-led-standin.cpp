// SPDX-License-Identifier: Apache-2.0
/*
 * bbb-led-standin: a temporary stand-in for OpenBMC's phosphor-led-sysfs on
 * the BeagleBone Black, for kernels without the LED driver.
 *
 * It publishes one standard xyz.openbmc_project.Led.Physical object per user
 * LED on the system D-Bus, with the same object names phosphor-led-sysfs
 * would use, and drives the LED's GPIO line directly:
 *
 *   /xyz/openbmc_project/led/physical/beaglebone_heartbeat_green  USR0 "[usr0 led]"
 *   /xyz/openbmc_project/led/physical/beaglebone_mmc0_green       USR1 "[usr1 led]"
 *   /xyz/openbmc_project/led/physical/beaglebone_usr2_green       USR2 "[usr2 led]"
 *   /xyz/openbmc_project/led/physical/beaglebone_usr3_green       USR3 "[usr3 led]"
 *
 * OpenBMC's LED group manager (phosphor-ledmanager) finds these objects
 * through the object mapper and sets their properties:
 *   State   "xyz.openbmc_project.Led.Physical.Action.Off" / ".On" / ".Blink"
 *   DutyOn  byte    percent of each blink period the LED is on
 *   Period  uint16  blink period in milliseconds
 *   Color   read-only, "xyz.openbmc_project.Led.Physical.Palette.Green"
 *
 * Every GPIO line is requested once at start-up and held until the program
 * exits, so the pins never fall back to inputs between changes.
 *
 * Built with sd-bus/sd-event (from libsystemd) for D-Bus and timers, and
 * libgpiod 1.6's C++ interface for GPIO.
 *
 * Usage: bbb-led-standin [--dry-run]
 *   --dry-run   don't touch GPIO; print what each LED would do instead
 */
#include <gpiod.hpp>
#include <systemd/sd-bus.h>
#include <systemd/sd-event.h>

#include <signal.h>

#include <array>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace {

constexpr const char* busName = "xyz.openbmc_project.LED.GpioStandIn";
constexpr const char* ledInterface = "xyz.openbmc_project.Led.Physical";
constexpr const char* pathPrefix = "/xyz/openbmc_project/led/physical/";
constexpr const char* actionPrefix = "xyz.openbmc_project.Led.Physical.Action.";
constexpr const char* colorGreen = "xyz.openbmc_project.Led.Physical.Palette.Green";

// Which D-Bus name goes with which GPIO line (names from the device tree).
struct LedSpec {
    const char* dbusName;
    const char* gpioLine;
};
constexpr std::array<LedSpec, 4> ledSpecs{{
    {"beaglebone_heartbeat_green", "[usr0 led]"},
    {"beaglebone_mmc0_green", "[usr1 led]"},
    {"beaglebone_usr2_green", "[usr2 led]"},
    {"beaglebone_usr3_green", "[usr3 led]"},
}};

enum class Action { Off, On, Blink };

const char* actionName(Action a)
{
    switch (a) {
    case Action::On:
        return "On";
    case Action::Blink:
        return "Blink";
    case Action::Off:
        break;
    }
    return "Off";
}

std::optional<Action> parseAction(const std::string& text)
{
    // Accept the full enum string D-Bus uses, e.g. "...Physical.Action.Blink".
    if (text.rfind(actionPrefix, 0) != 0)
        return std::nullopt;
    std::string tail = text.substr(std::strlen(actionPrefix));
    if (tail == "Off")
        return Action::Off;
    if (tail == "On")
        return Action::On;
    if (tail == "Blink")
        return Action::Blink;
    return std::nullopt;
}

class Led {
public:
    Led(sd_event* event, const LedSpec& spec, bool dryRun)
        : event_(event), name_(spec.dbusName), path_(std::string(pathPrefix) + spec.dbusName),
          dryRun_(dryRun)
    {
        if (!dryRun_) {
            line_ = gpiod::find_line(spec.gpioLine);
            if (!line_)
                throw std::runtime_error(std::string("GPIO line not found: ") + spec.gpioLine);
            // Take the line as an output, starting low (LED off), and keep it.
            line_.request({"bbb-led-standin", gpiod::line_request::DIRECTION_OUTPUT, 0}, 0);
        }
    }

    ~Led()
    {
        sd_event_source_unref(timer_);
        // libgpiod releases the line when `line_` is destroyed.
    }

    Led(const Led&) = delete;
    Led& operator=(const Led&) = delete;

    const std::string& path() const { return path_; }

    // ---- property access, called from the D-Bus handlers below ----

    Action state() const { return state_; }
    uint8_t dutyOn() const { return dutyOn_; }
    uint16_t period() const { return period_; }

    void setState(Action a)
    {
        state_ = a;
        apply();
    }
    void setDutyOn(uint8_t d)
    {
        dutyOn_ = d > 100 ? 100 : d;
        if (state_ == Action::Blink)
            apply();
    }
    void setPeriod(uint16_t p)
    {
        period_ = p;
        if (state_ == Action::Blink)
            apply();
    }

private:
    // Put the hardware into the current state.
    void apply()
    {
        stopTimer();
        std::cout << name_ << ": " << actionName(state_);
        if (state_ == Action::Blink)
            std::cout << " (period " << period_ << " ms, on " << int(dutyOn_) << " %)";
        std::cout << std::endl;

        if (state_ == Action::On) {
            write(true);
        } else if (state_ == Action::Off) {
            write(false);
        } else {
            uint32_t onMs = uint32_t(period_) * dutyOn_ / 100;
            if (period_ == 0 || onMs == 0) {
                write(false);			// never on
            } else if (onMs >= period_) {
                write(true);			// never off
            } else {
                blinkOn_ = true;
                write(true);
                startTimer(onMs);
            }
        }
    }

    void write(bool on)
    {
        if (dryRun_)
            std::cout << "  [dry-run] " << name_ << " = " << (on ? 1 : 0) << std::endl;
        else
            line_.set_value(on ? 1 : 0);
    }

    // ---- blinking: a one-shot sd-event timer that re-arms itself ----

    void startTimer(uint32_t ms)
    {
        sd_event_add_time_relative(event_, &timer_, CLOCK_MONOTONIC, uint64_t(ms) * 1000,
                                   0, &Led::onTimer, this);
    }

    void stopTimer()
    {
        if (timer_) {
            sd_event_source_set_enabled(timer_, SD_EVENT_OFF);
            timer_ = sd_event_source_unref(timer_);
        }
    }

    static int onTimer(sd_event_source*, uint64_t, void* userdata)
    {
        auto* self = static_cast<Led*>(userdata);
        self->timer_ = sd_event_source_unref(self->timer_);
        uint32_t onMs = uint32_t(self->period_) * self->dutyOn_ / 100;
        self->blinkOn_ = !self->blinkOn_;
        self->write(self->blinkOn_);
        self->startTimer(self->blinkOn_ ? onMs : self->period_ - onMs);
        return 0;
    }

    sd_event* event_;
    std::string name_;
    std::string path_;
    bool dryRun_;
    gpiod::line line_;
    sd_event_source* timer_ = nullptr;
    bool blinkOn_ = false;

    // Defaults from the Led.Physical interface definition.
    Action state_ = Action::Off;
    uint8_t dutyOn_ = 50;
    uint16_t period_ = 1000;
};

// ---- D-Bus property handlers (sd-bus calls these with userdata = Led*) ----

int getProperty(sd_bus*, const char*, const char*, const char* property,
                sd_bus_message* reply, void* userdata, sd_bus_error*)
{
    auto* led = static_cast<Led*>(userdata);
    if (std::strcmp(property, "State") == 0)
        return sd_bus_message_append(
            reply, "s", (std::string(actionPrefix) + actionName(led->state())).c_str());
    if (std::strcmp(property, "DutyOn") == 0)
        return sd_bus_message_append(reply, "y", led->dutyOn());
    if (std::strcmp(property, "Period") == 0)
        return sd_bus_message_append(reply, "q", led->period());
    if (std::strcmp(property, "Color") == 0)
        return sd_bus_message_append(reply, "s", colorGreen);
    return -EINVAL;
}

int setProperty(sd_bus* bus, const char* path, const char* interface, const char* property,
                sd_bus_message* value, void* userdata, sd_bus_error* error)
{
    auto* led = static_cast<Led*>(userdata);
    int r;
    if (std::strcmp(property, "State") == 0) {
        const char* text = nullptr;
        if ((r = sd_bus_message_read(value, "s", &text)) < 0)
            return r;
        auto action = parseAction(text);
        if (!action)
            return sd_bus_error_setf(error, SD_BUS_ERROR_INVALID_ARGS,
                                     "Unknown State value: %s", text);
        led->setState(*action);
    } else if (std::strcmp(property, "DutyOn") == 0) {
        uint8_t d;
        if ((r = sd_bus_message_read(value, "y", &d)) < 0)
            return r;
        led->setDutyOn(d);
    } else if (std::strcmp(property, "Period") == 0) {
        uint16_t p;
        if ((r = sd_bus_message_read(value, "q", &p)) < 0)
            return r;
        led->setPeriod(p);
    } else {
        return -EINVAL;
    }
    // Tell anyone watching (busctl monitor, other programs) that it changed.
    sd_bus_emit_properties_changed(bus, path, interface, property, nullptr);
    return 1;
}

// The interface description: which properties exist, their D-Bus types, and
// which functions read and write them.
const sd_bus_vtable ledVtable[] = {
    SD_BUS_VTABLE_START(0),
    SD_BUS_WRITABLE_PROPERTY("State", "s", getProperty, setProperty, 0,
                             SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE),
    SD_BUS_WRITABLE_PROPERTY("DutyOn", "y", getProperty, setProperty, 0,
                             SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE),
    SD_BUS_WRITABLE_PROPERTY("Period", "q", getProperty, setProperty, 0,
                             SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE),
    SD_BUS_PROPERTY("Color", "s", getProperty, 0, SD_BUS_VTABLE_PROPERTY_CONST),
    SD_BUS_VTABLE_END,
};

int check(int r, const char* what)
{
    if (r < 0)
        throw std::runtime_error(std::string(what) + ": " + std::strerror(-r));
    return r;
}

} // namespace

int main(int argc, char* argv[])
{
    bool dryRun = argc > 1 && std::strcmp(argv[1], "--dry-run") == 0;
    sd_event* event = nullptr;
    sd_bus* bus = nullptr;
    int result = 0;

    try {
        check(sd_event_default(&event), "sd_event_default");

        // Stop cleanly on SIGTERM (systemctl stop) and SIGINT (Ctrl-C).
        sigset_t mask;
        sigemptyset(&mask);
        sigaddset(&mask, SIGTERM);
        sigaddset(&mask, SIGINT);
        sigprocmask(SIG_BLOCK, &mask, nullptr);
        check(sd_event_add_signal(event, nullptr, SIGTERM, nullptr, nullptr), "SIGTERM");
        check(sd_event_add_signal(event, nullptr, SIGINT, nullptr, nullptr), "SIGINT");

        // Take all four GPIO lines (fails early if one is busy or missing).
        std::vector<std::unique_ptr<Led>> leds;
        for (const auto& spec : ledSpecs)
            leds.push_back(std::make_unique<Led>(event, spec, dryRun));

        check(sd_bus_open_system(&bus), "connect to system D-Bus");

        // Publish the objects FIRST, then claim the bus name: the object
        // mapper looks at our objects as soon as the name appears.
        for (auto& led : leds)
            check(sd_bus_add_object_vtable(bus, nullptr, led->path().c_str(), ledInterface,
                                           ledVtable, led.get()),
                  "add object");
        check(sd_bus_request_name(bus, busName, 0), "request bus name");

        check(sd_bus_attach_event(bus, event, SD_EVENT_PRIORITY_NORMAL), "attach bus");
        std::cout << "bbb-led-standin: serving " << leds.size() << " LEDs as " << busName
                  << (dryRun ? " (dry run: no GPIO)" : "") << std::endl;

        check(sd_event_loop(event), "event loop");	// runs until a signal arrives
        std::cout << "bbb-led-standin: stopping" << std::endl;
        // `leds` is destroyed here: timers stop and the GPIO lines are released.
    } catch (const std::exception& e) {
        std::cerr << "bbb-led-standin: error: " << e.what() << std::endl;
        result = 1;
    }
    sd_bus_flush_close_unref(bus);
    sd_event_unref(event);
    return result;
}
