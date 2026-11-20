// SPDX-License-Identifier: Apache-2.0
/*
 * gpio-blink-uapi (C++): blink a GPIO line using the kernel's GPIO interface
 * (<linux/gpio.h>, "v2") directly, with no library.
 *
 * The line is requested once and held until the program ends, so it never
 * falls back to an input between "on" and "off".
 *
 * Usage: gpio-blink-uapi-cpp [LINE-NAME] [COUNT] [HALF-PERIOD-MS]
 *   LINE-NAME       device-tree name of the line   (default "[usr3 led]")
 *   COUNT           how many times to blink        (default 5)
 *   HALF-PERIOD-MS  time on, and time off, in ms   (default 500)
 */
#include <linux/gpio.h>     // kernel GPIO structures and ioctl codes
#include <sys/ioctl.h>      // ioctl()
#include <fcntl.h>          // open(), O_RDWR, O_CLOEXEC
#include <unistd.h>         // close()

#include <cerrno>           // errno
#include <chrono>           // std::chrono::milliseconds
#include <cstring>          // std::strncpy, std::strcmp
#include <iostream>         // std::cout, std::cerr
#include <optional>         // std::optional
#include <string>           // std::string, std::stol
#include <system_error>     // std::system_error
#include <thread>           // std::this_thread::sleep_for
#include <utility>          // std::exchange

// Owns one open file descriptor and closes it automatically when it goes
// out of scope ("RAII"), so no exit path can forget to release the line.
class Fd {
public:
	explicit Fd(int fd = -1) : fd_(fd) {}
	~Fd() { if (fd_ >= 0) ::close(fd_); }
	Fd(Fd &&other) noexcept : fd_(std::exchange(other.fd_, -1)) {}
	Fd &operator=(Fd &&other) noexcept
	{
		if (this != &other) {
			if (fd_ >= 0) ::close(fd_);
			fd_ = std::exchange(other.fd_, -1);
		}
		return *this;
	}
	Fd(const Fd &) = delete;			// one owner only: no copies
	Fd &operator=(const Fd &) = delete;
	int get() const { return fd_; }
	explicit operator bool() const { return fd_ >= 0; }
private:
	int fd_;
};

// Throw a C++ exception carrying errno's message, e.g. "Device or resource busy".
[[noreturn]] static void throw_errno(const std::string &what)
{
	throw std::system_error(errno, std::generic_category(), what);
}

struct FoundLine {
	Fd chip;		// the open /dev/gpiochipN
	std::string path;	// e.g. "/dev/gpiochip0"
	unsigned int offset;	// line number within that chip
};

// Search /dev/gpiochip0, 1, 2 ... for a line called `name`.
static std::optional<FoundLine> find_line(const std::string &name)
{
	for (int n = 0; n < 32; n++) {
		std::string path = "/dev/gpiochip" + std::to_string(n);
		Fd chip(::open(path.c_str(), O_RDWR | O_CLOEXEC));
		if (!chip)
			continue;			// no such chip: try the next number

		gpiochip_info info{};			// {} = all fields zero
		if (::ioctl(chip.get(), GPIO_GET_CHIPINFO_IOCTL, &info) < 0)
			continue;

		for (unsigned int i = 0; i < info.lines; i++) {
			gpio_v2_line_info line{};	// zeroed: kernel requires padding = 0
			line.offset = i;
			if (::ioctl(chip.get(), GPIO_V2_GET_LINEINFO_IOCTL, &line) < 0)
				continue;
			if (name == line.name)
				return FoundLine{std::move(chip), path, i};
		}
	}						// `chip` closes itself here if not returned
	return std::nullopt;
}

// Request one line as an output with a starting value; returns the line handle.
static Fd request_output(const FoundLine &found, int initial)
{
	gpio_v2_line_request req{};
	req.offsets[0] = found.offset;			// which line on this chip
	req.num_lines = 1;				// just that one
	std::strncpy(req.consumer, "gpio-blink-uapi-cpp", sizeof(req.consumer) - 1);
	req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT;	// make it an output
	req.config.num_attrs = 1;			// one extra setting:
	req.config.attrs[0].mask = 1;			//   for line #0 ...
	req.config.attrs[0].attr.id = GPIO_V2_LINE_ATTR_ID_OUTPUT_VALUES;
	req.config.attrs[0].attr.values = initial ? 1 : 0;	//   ... start at this level

	if (::ioctl(found.chip.get(), GPIO_V2_GET_LINE_IOCTL, &req) < 0)
		throw_errno("cannot request " + found.path + " line " + std::to_string(found.offset));
	return Fd(req.fd);
}

static void set_value(const Fd &line, int value)
{
	gpio_v2_line_values vals{};
	vals.mask = 1;			// change line #0 of our request ...
	vals.bits = value ? 1 : 0;	// ... to this level
	if (::ioctl(line.get(), GPIO_V2_LINE_SET_VALUES_IOCTL, &vals) < 0)
		throw_errno("cannot set value");
}

int main(int argc, char *argv[])
{
	try {
		const std::string name = argc > 1 ? argv[1] : "[usr3 led]";
		const long count = argc > 2 ? std::stol(argv[2]) : 5;
		const std::chrono::milliseconds half(argc > 3 ? std::stol(argv[3]) : 500);

		std::optional<FoundLine> found = find_line(name);
		if (!found) {
			std::cerr << "no GPIO line named \"" << name << "\" found\n";
			return 1;
		}
		std::cout << "found \"" << name << "\": " << found->path
			  << " line " << found->offset << std::endl;

		Fd line = request_output(*found, 0);
		found.reset();		// close the chip; the line handle stays valid

		for (long i = 0; i < count; i++) {
			set_value(line, 1);
			std::this_thread::sleep_for(half);
			set_value(line, 0);
			std::this_thread::sleep_for(half);
		}
		// `line` is closed here automatically: the line is released
		// (on this chip it becomes an input).
	} catch (const std::exception &e) {	// errors from throw_errno() or std::stol()
		std::cerr << "error: " << e.what() << '\n';
		return 1;
	}
	std::cout << "done" << std::endl;
	return 0;
}
