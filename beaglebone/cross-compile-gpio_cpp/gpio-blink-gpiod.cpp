// SPDX-License-Identifier: Apache-2.0
/*
 * gpio-blink-gpiod (C++): blink a GPIO line using libgpiod 1.6's C++
 * interface (<gpiod.hpp>), the same library version OpenBMC uses.
 *
 * The line is requested once and held until the program ends, so it never
 * falls back to an input between "on" and "off".
 *
 * Usage: gpio-blink-gpiod-cpp [LINE-NAME] [COUNT] [HALF-PERIOD-MS]
 *   LINE-NAME       device-tree name of the line   (default "[usr3 led]")
 *   COUNT           how many times to blink        (default 5)
 *   HALF-PERIOD-MS  time on, and time off, in ms   (default 500)
 */
#include <gpiod.hpp>        // libgpiod 1.6 C++ interface

#include <chrono>           // std::chrono::milliseconds
#include <iostream>         // std::cout, std::cerr
#include <string>           // std::string, std::stol
#include <thread>           // std::this_thread::sleep_for

int main(int argc, char *argv[])
{
	try {
		const std::string name = argc > 1 ? argv[1] : "[usr3 led]";
		const long count = argc > 2 ? std::stol(argv[2]) : 5;
		const std::chrono::milliseconds half(argc > 3 ? std::stol(argv[3]) : 500);

		// Search every /dev/gpiochipN for a line with this name.
		gpiod::line line = gpiod::find_line(name);
		if (!line) {				// empty object = not found
			std::cerr << "no GPIO line named \"" << name << "\" found\n";
			return 1;
		}
		std::cout << "found \"" << name << "\": " << line.get_chip().name()
			  << " line " << line.offset() << std::endl;

		// Take the line as an output, owner "gpio-blink-gpiod-cpp", starting low.
		line.request({"gpio-blink-gpiod-cpp",			// owner name (gpioinfo)
			      gpiod::line_request::DIRECTION_OUTPUT,	// as an output
			      0},					// no extra flags
			     0);					// starting value: low

		for (long i = 0; i < count; i++) {
			line.set_value(1);
			std::this_thread::sleep_for(half);
			line.set_value(0);
			std::this_thread::sleep_for(half);
		}
		line.release();		// give the line back (on this chip it becomes an input);
					// also happens automatically when `line` goes away
	} catch (const std::exception &e) {	// libgpiod reports errors as exceptions
		std::cerr << "error: " << e.what() << '\n';
		return 1;
	}
	std::cout << "done" << std::endl;
	return 0;
}
