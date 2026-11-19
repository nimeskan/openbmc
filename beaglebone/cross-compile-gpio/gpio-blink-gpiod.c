// SPDX-License-Identifier: Apache-2.0
/*
 * gpio-blink-gpiod: blink a GPIO line using libgpiod 1.6 (<gpiod.h>),
 * the same library version and API that OpenBMC uses.
 *
 * The line is requested once and held until the program ends, so it never
 * falls back to an input between "on" and "off".
 *
 * Usage: gpio-blink-gpiod [LINE-NAME] [COUNT] [HALF-PERIOD-MS]
 *   LINE-NAME       device-tree name of the line   (default "[usr3 led]")
 *   COUNT           how many times to blink        (default 5)
 *   HALF-PERIOD-MS  time on, and time off, in ms   (default 500)
 */
#include <gpiod.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char *argv[])
{
	const char *name = argc > 1 ? argv[1] : "[usr3 led]";
	long count = argc > 2 ? strtol(argv[2], NULL, 10) : 5;
	long half_ms = argc > 3 ? strtol(argv[3], NULL, 10) : 500;
	struct gpiod_line *line;

	/* Search every /dev/gpiochipN for a line with this name. */
	line = gpiod_line_find(name);
	if (!line) {
		fprintf(stderr, "no GPIO line named \"%s\" found\n", name);
		return 1;
	}
	printf("found \"%s\": %s line %u\n", name,
	       gpiod_chip_name(gpiod_line_get_chip(line)), gpiod_line_offset(line));

	/* Take the line as an output, owner name "gpio-blink-gpiod", starting low. */
	if (gpiod_line_request_output(line, "gpio-blink-gpiod", 0) < 0) {
		perror("cannot request line");
		gpiod_line_close_chip(line);
		return 1;
	}

	for (long i = 0; i < count; i++) {
		if (gpiod_line_set_value(line, 1) < 0)
			perror("set high");
		usleep(half_ms * 1000);
		if (gpiod_line_set_value(line, 0) < 0)
			perror("set low");
		usleep(half_ms * 1000);
	}

	gpiod_line_release(line);	/* give the line back (on this chip it becomes an input) */
	gpiod_line_close_chip(line);	/* close the chip that gpiod_line_find() opened */
	printf("done\n");
	return 0;
}
