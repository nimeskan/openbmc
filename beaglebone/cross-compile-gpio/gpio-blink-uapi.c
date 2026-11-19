// SPDX-License-Identifier: Apache-2.0
/*
 * gpio-blink-uapi: blink a GPIO line using the kernel's GPIO interface
 * (<linux/gpio.h>, "v2") directly, with no library.
 *
 * The line is requested once and held until the program ends, so it never
 * falls back to an input between "on" and "off".
 *
 * Usage: gpio-blink-uapi [LINE-NAME] [COUNT] [HALF-PERIOD-MS]
 *   LINE-NAME       device-tree name of the line   (default "[usr3 led]")
 *   COUNT           how many times to blink        (default 5)
 *   HALF-PERIOD-MS  time on, and time off, in ms   (default 500)
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

static void sleep_ms(long ms)
{
	struct timespec ts = { .tv_sec = ms / 1000, .tv_nsec = (ms % 1000) * 1000000L };

	while (nanosleep(&ts, &ts) < 0 && errno == EINTR)
		;	/* interrupted early: sleep for the time that is left */
}

/*
 * Search /dev/gpiochip0, 1, 2 ... for a line called NAME.
 * On success returns the open chip file descriptor, and stores the line's
 * number within that chip in *offset and the chip's path in path.
 */
static int find_line(const char *name, char *path, size_t path_len, unsigned int *offset)
{
	for (int n = 0; n < 32; n++) {
		struct gpiochip_info chip;
		int fd;

		snprintf(path, path_len, "/dev/gpiochip%d", n);
		fd = open(path, O_RDWR | O_CLOEXEC);
		if (fd < 0)
			continue;		/* no such chip: try the next number */

		memset(&chip, 0, sizeof(chip));
		if (ioctl(fd, GPIO_GET_CHIPINFO_IOCTL, &chip) < 0) {
			close(fd);
			continue;
		}

		for (unsigned int i = 0; i < chip.lines; i++) {
			struct gpio_v2_line_info info;

			memset(&info, 0, sizeof(info));	/* kernel requires padding = 0 */
			info.offset = i;
			if (ioctl(fd, GPIO_V2_GET_LINEINFO_IOCTL, &info) < 0)
				continue;
			if (strcmp(info.name, name) == 0) {
				*offset = i;
				return fd;
			}
		}
		close(fd);
	}
	return -1;
}

static int set_value(int line_fd, int value)
{
	struct gpio_v2_line_values vals;

	memset(&vals, 0, sizeof(vals));
	vals.mask = 1;			/* change line #0 of our request ... */
	vals.bits = value ? 1 : 0;	/* ... to this level */
	return ioctl(line_fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &vals);
}

int main(int argc, char *argv[])
{
	const char *name = argc > 1 ? argv[1] : "[usr3 led]";
	long count = argc > 2 ? strtol(argv[2], NULL, 10) : 5;
	long half_ms = argc > 3 ? strtol(argv[3], NULL, 10) : 500;
	struct gpio_v2_line_request req;
	char path[32];
	unsigned int offset;
	int chip_fd;

	chip_fd = find_line(name, path, sizeof(path), &offset);
	if (chip_fd < 0) {
		fprintf(stderr, "no GPIO line named \"%s\" found\n", name);
		return 1;
	}
	printf("found \"%s\": %s line %u\n", name, path, offset);

	memset(&req, 0, sizeof(req));
	req.offsets[0] = offset;			/* which line on this chip */
	req.num_lines = 1;				/* just that one */
	strncpy(req.consumer, "gpio-blink-uapi", sizeof(req.consumer) - 1);
	req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT;	/* make it an output */
	req.config.num_attrs = 1;			/* one extra setting: */
	req.config.attrs[0].mask = 1;			/*   for line #0 ... */
	req.config.attrs[0].attr.id = GPIO_V2_LINE_ATTR_ID_OUTPUT_VALUES;
	req.config.attrs[0].attr.values = 0;		/*   ... start low (off) */

	if (ioctl(chip_fd, GPIO_V2_GET_LINE_IOCTL, &req) < 0) {
		fprintf(stderr, "cannot request %s line %u: %s\n", path, offset, strerror(errno));
		close(chip_fd);
		return 1;
	}
	close(chip_fd);		/* req.fd now represents the line; the chip fd is not needed */

	for (long i = 0; i < count; i++) {
		if (set_value(req.fd, 1) < 0)
			perror("set high");
		sleep_ms(half_ms);
		if (set_value(req.fd, 0) < 0)
			perror("set low");
		sleep_ms(half_ms);
	}

	close(req.fd);		/* release the line (on this chip it becomes an input) */
	printf("done\n");
	return 0;
}
