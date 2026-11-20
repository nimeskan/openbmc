// SPDX-License-Identifier: Apache-2.0
//! bbb-led-standin-rs: a temporary stand-in for OpenBMC's phosphor-led-sysfs
//! on the BeagleBone Black, for kernels without the LED driver.
//!
//! It publishes one standard `xyz.openbmc_project.Led.Physical` object per
//! user LED on the system D-Bus, with the same object names
//! phosphor-led-sysfs would use, and drives the LED's GPIO line directly:
//!
//!   /xyz/openbmc_project/led/physical/beaglebone_heartbeat_green  USR0 "[usr0 led]"
//!   /xyz/openbmc_project/led/physical/beaglebone_mmc0_green       USR1 "[usr1 led]"
//!   /xyz/openbmc_project/led/physical/beaglebone_usr2_green       USR2 "[usr2 led]"
//!   /xyz/openbmc_project/led/physical/beaglebone_usr3_green       USR3 "[usr3 led]"
//!
//! OpenBMC's LED group manager (phosphor-ledmanager) finds these objects
//! through the object mapper and sets their properties:
//!   State   "xyz.openbmc_project.Led.Physical.Action.Off" / ".On" / ".Blink"
//!   DutyOn  byte    percent of each blink period the LED is on
//!   Period  uint16  blink period in milliseconds
//!   Color   read-only, "xyz.openbmc_project.Led.Physical.Palette.Green"
//!
//! Every GPIO line is requested once at start-up and held until the program
//! exits, so the pins never fall back to inputs between changes.
//!
//! Built with zbus (D-Bus) and gpiocdev (GPIO), both written in Rust.
//!
//! Usage: bbb-led-standin-rs [--dry-run]
//!   --dry-run   don't touch GPIO; print what each LED would do instead

use gpiocdev::line::Value;
use std::sync::{Arc, Condvar, Mutex};
use std::time::Duration;
use std::{env, thread};
use zbus::{blocking::connection, fdo, interface};

const BUS_NAME: &str = "xyz.openbmc_project.LED.GpioStandIn";
const PATH_PREFIX: &str = "/xyz/openbmc_project/led/physical/";
const ACTION_PREFIX: &str = "xyz.openbmc_project.Led.Physical.Action.";
const COLOR_GREEN: &str = "xyz.openbmc_project.Led.Physical.Palette.Green";

/// Which D-Bus name goes with which GPIO line (names from the device tree).
const LEDS: [(&str, &str); 4] = [
    ("beaglebone_heartbeat_green", "[usr0 led]"),
    ("beaglebone_mmc0_green", "[usr1 led]"),
    ("beaglebone_usr2_green", "[usr2 led]"),
    ("beaglebone_usr3_green", "[usr3 led]"),
];

#[derive(Clone, Copy, PartialEq, Debug)]
enum Action {
    Off,
    On,
    Blink,
}

/// The LED's settings, shared between the D-Bus side and the LED's worker
/// thread. `generation` goes up on every change, so the worker can tell
/// that it has to start over.
#[derive(Clone, Copy)]
struct Settings {
    state: Action,
    duty_on: u8,
    period: u16,
    generation: u64,
}

type Shared = Arc<(Mutex<Settings>, Condvar)>;

/// Where the LED's level goes: a held GPIO line, or the screen (--dry-run).
enum Output {
    Gpio(gpiocdev::Request),
    DryRun(String),
}

impl Output {
    fn write(&self, on: bool) {
        match self {
            Output::Gpio(req) => {
                let value = if on { Value::Active } else { Value::Inactive };
                if let Err(e) = req.set_lone_value(value) {
                    eprintln!("GPIO write failed: {e}");
                }
            }
            Output::DryRun(name) => println!("  [dry-run] {name} = {}", on as u8),
        }
    }
}

/// The worker thread for one LED: puts the hardware into the current state,
/// toggling it for Blink, and starts over whenever the settings change.
fn run_led(name: String, output: Output, shared: Shared) {
    let (lock, changed) = &*shared;
    let mut settings = *lock.lock().unwrap();
    loop {
        let s = settings;
        match s.state {
            Action::Blink => println!(
                "{name}: Blink (period {} ms, on {} %)",
                s.period, s.duty_on
            ),
            other => println!("{name}: {other:?}"),
        }
        let on_ms = u64::from(s.period) * u64::from(s.duty_on.min(100)) / 100;
        let off_ms = u64::from(s.period) - on_ms;

        // (level, how long to hold it) steps; None = hold until the next change.
        let steps: Vec<(bool, Option<u64>)> = match s.state {
            Action::Off => vec![(false, None)],
            Action::On => vec![(true, None)],
            Action::Blink if s.period == 0 || on_ms == 0 => vec![(false, None)],
            Action::Blink if off_ms == 0 => vec![(true, None)],
            Action::Blink => vec![(true, Some(on_ms)), (false, Some(off_ms))],
        };

        // Play the steps (repeating them for Blink) until the settings change.
        'play: loop {
            for &(level, hold) in &steps {
                output.write(level);
                let guard = lock.lock().unwrap();
                let guard = match hold {
                    // Wait until the generation changes ...
                    None => changed
                        .wait_while(guard, |cur| cur.generation == s.generation)
                        .unwrap(),
                    // ... or until the time is up, whichever comes first.
                    Some(ms) => {
                        changed
                            .wait_timeout_while(guard, Duration::from_millis(ms), |cur| {
                                cur.generation == s.generation
                            })
                            .unwrap()
                            .0
                    }
                };
                if guard.generation != s.generation {
                    settings = *guard;
                    break 'play;
                }
            }
        }
    }
}

/// The D-Bus object for one LED. zbus calls these methods when another
/// program reads or writes a property.
struct LedObject {
    shared: Shared,
}

impl LedObject {
    /// Change the settings. The worker only has to start over if the
    /// visible behaviour changes: always for State, for DutyOn/Period only
    /// while blinking (like phosphor-led-sysfs, they're stored otherwise).
    fn update(&self, change: impl FnOnce(&mut Settings)) {
        let (lock, changed) = &*self.shared;
        let mut s = lock.lock().unwrap();
        let before = s.state;
        change(&mut s);
        if s.state != before || s.state == Action::Blink {
            s.generation += 1;
            changed.notify_all(); // wake the worker thread
        }
    }
}

#[interface(name = "xyz.openbmc_project.Led.Physical")]
impl LedObject {
    #[zbus(property)]
    fn state(&self) -> String {
        let s = self.shared.0.lock().unwrap();
        format!("{ACTION_PREFIX}{:?}", s.state)
    }

    #[zbus(property)]
    fn set_state(&mut self, value: String) -> fdo::Result<()> {
        let action = match value.strip_prefix(ACTION_PREFIX) {
            Some("Off") => Action::Off,
            Some("On") => Action::On,
            Some("Blink") => Action::Blink,
            _ => {
                return Err(fdo::Error::InvalidArgs(format!(
                    "Unknown State value: {value}"
                )))
            }
        };
        let (lock, changed) = &*self.shared;
        let mut s = lock.lock().unwrap();
        s.state = action;
        s.generation += 1; // always re-apply a State write
        changed.notify_all();
        Ok(())
    }

    #[zbus(property)]
    fn duty_on(&self) -> u8 {
        self.shared.0.lock().unwrap().duty_on
    }

    #[zbus(property)]
    fn set_duty_on(&mut self, value: u8) {
        self.update(|s| s.duty_on = value.min(100));
    }

    #[zbus(property)]
    fn period(&self) -> u16 {
        self.shared.0.lock().unwrap().period
    }

    #[zbus(property)]
    fn set_period(&mut self, value: u16) {
        self.update(|s| s.period = value);
    }

    #[zbus(property(emits_changed_signal = "const"))]
    fn color(&self) -> String {
        COLOR_GREEN.to_string()
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let dry_run = env::args().nth(1).as_deref() == Some("--dry-run");

    // Start building the D-Bus connection; objects are added below.
    let mut builder = connection::Builder::system()?;

    for (dbus_name, gpio_line) in LEDS {
        // Take the GPIO line as an output, starting low (LED off), and keep it.
        let output = if dry_run {
            Output::DryRun(dbus_name.to_string())
        } else {
            let found = gpiocdev::find_named_line(gpio_line)
                .ok_or_else(|| format!("GPIO line not found: {gpio_line}"))?;
            Output::Gpio(
                gpiocdev::Request::builder()
                    .with_found_line(&found)
                    .with_consumer("bbb-led-standin-rs")
                    .as_output(Value::Inactive)
                    .request()?,
            )
        };

        // Defaults from the Led.Physical interface definition.
        let shared: Shared = Arc::new((
            Mutex::new(Settings { state: Action::Off, duty_on: 50, period: 1000, generation: 0 }),
            Condvar::new(),
        ));

        let worker_shared = Arc::clone(&shared);
        let name = dbus_name.to_string();
        thread::spawn(move || run_led(name, output, worker_shared));

        builder = builder.serve_at(format!("{PATH_PREFIX}{dbus_name}"), LedObject { shared })?;
    }

    // Claim the bus name. zbus registers the objects above before requesting
    // the name, so the object mapper sees them as soon as the name appears.
    let _connection = builder.name(BUS_NAME)?.build()?;
    println!(
        "bbb-led-standin-rs: serving {} LEDs as {BUS_NAME}{}",
        LEDS.len(),
        if dry_run { " (dry run: no GPIO)" } else { "" }
    );

    // zbus answers D-Bus calls on its own thread; this one just waits.
    loop {
        thread::park();
    }
}

fn main() {
    if let Err(e) = run() {
        eprintln!("bbb-led-standin-rs: error: {e}");
        std::process::exit(1);
    }
}
