# Cross-compile a GPIO program

Our OpenBMC image has **no compiler**: no `gcc`, no header files, no `make`.
So C programs for the BeagleBone are built on your **Ubuntu PC** with a
**cross-compiler** (a compiler that runs on the PC but produces programs for
the board's ARM processor), then copied to the board with `scp`.

This guide builds **two programs that do the same job**, by two different
routes:

| | Path A: `gpio-blink-uapi` | Path B: `gpio-blink-gpiod` |
| --- | --- | --- |
| Talks to the kernel through | `<linux/gpio.h>` directly (the kernel's GPIO interface, "v2") | `<gpiod.h>`: **libgpiod 1.6**, the same library and version OpenBMC uses |
| Extra things to install on the PC | Nothing beyond the cross-compiler | Build libgpiod 1.6.5 for ARM (a few minutes, once) |
| Code | Longer: you fill in the kernel's structures yourself | Shorter: one function call per step |
| Program size | About 8 KB | About 95 KB (libgpiod is built into it) |

Both programs:
1. find a GPIO line **by its name** (default `[usr3 led]`, the USR3 LED);
2. **reserve it once** as an output, starting low;
3. blink it, then release it when finished.

Because the line is held the whole time, it **never falls back to an input**
between "on" and "off". That's the glitch-free control that `gpioset` can't
give you (see the [LED guide](turn-on-led-guide.md#4d-important-the-pin-is-only-yours-while-gpioset-runs)).

The source files are in [`cross-compile-gpio/`](cross-compile-gpio/):
* [`gpio-blink-uapi.c`](cross-compile-gpio/gpio-blink-uapi.c)
* [`gpio-blink-gpiod.c`](cross-compile-gpio/gpio-blink-gpiod.c)

> **What was tested, and how.**
> * **The build commands:** every command in sections 2–5 was run on
>   **Ubuntu 24.04** exactly as written, and both programs built.
> * **Against the board's C library:** both programs were run against the C
>   library copied from our released image (glibc 2.43), in an ARM emulator
>   (`qemu-arm`). They start, search for the line, and report correctly when
>   it isn't there (the emulator has no GPIO hardware).
> * **Path A's logic:** run with the kernel's GPIO calls faked out. It found
>   the line on the second chip, requested it as an output starting low, and
>   switched it high and low the right number of times, with the right timing.
> * **Not yet:** running either program on the real board.

---

## Contents

1. [How cross-compiling works](#1-how-cross-compiling-works)
2. [One-time setup on Ubuntu](#2-one-time-setup-on-ubuntu)
3. [Get the source files](#3-get-the-source-files)
4. [Path A: `<linux/gpio.h>`, no library](#4-path-a-linuxgpioh-no-library)
5. [Path B: libgpiod 1.6](#5-path-b-libgpiod-16)
6. [Run them on the board](#6-run-them-on-the-board)
7. [How the code works](#7-how-the-code-works)
8. [Checking a program before you copy it](#8-checking-a-program-before-you-copy-it)
9. [Troubleshooting](#9-troubleshooting)
10. [What comes next](#10-what-comes-next)

---

## 1. How cross-compiling works

```
   Ubuntu PC (x86-64)                                   BeagleBone (ARM)
 ┌────────────────────────────────────────┐          ┌────────────────────────────┐
 │ gpio-blink-uapi.c   (your C source)    │          │                            │
 │        │                               │          │ /home/root/gpio-blink-uapi │
 │        ▼                               │   scp    │        │                   │
 │ arm-linux-gnueabihf-gcc ──► program  ──┼─────────►│        ▼ runs with the     │
 │   (cross-compiler: runs on the PC,     │          │   board's C library        │
 │    produces 32-bit ARM code)           │          │   (glibc 2.43) and kernel  │
 └────────────────────────────────────────┘          └────────────────────────────┘
```

* **Why a special compiler?** Your PC's processor (x86-64) and the board's
  (32-bit ARM Cortex-A8) understand different machine code. A normal `gcc`
  produces code for the PC. `arm-linux-gnueabihf-gcc` produces code for
  32-bit ARM Linux:
  * `arm`: 32-bit ARM;
  * `linux-gnu`: Linux with the GNU C library (glibc);
  * `eabi`: ARM's standard way for programs and libraries to call each other;
  * `hf`: "hard float", meaning floating-point numbers are passed in the
    processor's floating-point registers.

  That matches our image: its programs use the loader
  `/lib/ld-linux-armhf.so.3`.
* **Matching C library versions.** The programs here use the board's own
  glibc at run time. A program built against an **older** glibc runs on a
  **newer** one, not the other way round. The board has glibc **2.43**.
  Ubuntu 24.04's cross-compiler produced programs needing at most
  **GLIBC_2.38**, so they run. (Section 8 shows how to check.)
* **Headers and libraries come from the PC.** `<linux/gpio.h>` comes with the
  cross-compiler packages. libgpiod 1.6 doesn't (Ubuntu 24.04 ships the
  incompatible 2.x), so Path B builds it from source.

---

## 2. One-time setup on Ubuntu

```sh
sudo apt update
sudo apt install gcc-arm-linux-gnueabihf build-essential wget xz-utils file
```

| Package | What it gives you |
| --- | --- |
| `gcc-arm-linux-gnueabihf` | The cross-compiler `arm-linux-gnueabihf-gcc`, plus the matching ARM C library and kernel headers (including `<linux/gpio.h>`), and tools such as `arm-linux-gnueabihf-readelf` |
| `build-essential` | `make` and the PC's own `gcc`; libgpiod's build (Path B) needs `make` |
| `wget` | Downloads files from the web (libgpiod's source in Path B) |
| `xz-utils` | Unpacks `.tar.xz` archives |
| `file` | Tells you what kind of program a file is (section 8) |

Check that the cross-compiler works:

```sh
arm-linux-gnueabihf-gcc --version
```

It prints its version, e.g.
`arm-linux-gnueabihf-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`. Any
recent version is fine.

Make a working folder for this guide:

```sh
mkdir -p ~/bbb-gpio
cd ~/bbb-gpio
```

`mkdir -p` creates the folder (no error if it already exists), and `~` is
your home folder. **All the commands below are run in `~/bbb-gpio` unless
they say otherwise.**

---

## 3. Get the source files

Download the two example programs from this repository:

```sh
wget https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/cross-compile-gpio/gpio-blink-uapi.c
wget https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/cross-compile-gpio/gpio-blink-gpiod.c
```

`raw.githubusercontent.com` serves a repository's files as plain text, so
`wget` saves the source itself rather than a web page. If you have the
repository cloned, copy them from its `beaglebone/cross-compile-gpio/` folder
instead.

---

## 4. Path A: `<linux/gpio.h>`, no library

### 4a. Compile

```sh
arm-linux-gnueabihf-gcc -Wall -Wextra -O2 -o gpio-blink-uapi gpio-blink-uapi.c
```

| Part | Meaning |
| --- | --- |
| `arm-linux-gnueabihf-gcc` | The cross-compiler (section 1) |
| `-Wall -Wextra` | Turn on warnings about suspicious code. There should be none. |
| `-O2` | Normal optimisation |
| `-o gpio-blink-uapi` | Name of the program to produce |
| `gpio-blink-uapi.c` | The source file |

No `-I` (where to find headers) or `-l` (which libraries to link) is needed:
`<linux/gpio.h>` and the C library come with the cross-compiler.

### 4b. Check it

```sh
file gpio-blink-uapi
```

Expected: `ELF 32-bit LSB pie executable, ARM, EABI5 … dynamically linked,
interpreter /lib/ld-linux-armhf.so.3 …`. **ARM** is what matters. If it says
`x86-64`, the normal `gcc` was used by mistake.

### 4c. Copy it to the board

```sh
scp gpio-blink-uapi root@evb-beaglebone.local:
```

The `:` with nothing after it means the board's home folder for `root`,
which is `/home/root`. Run this on the **PC**, not in an SSH session on the
board.

Then go to [section 6](#6-run-them-on-the-board) to run it.

---

## 5. Path B: libgpiod 1.6

### 5a. Why build libgpiod yourself?

* The board has **libgpiod 1.6.5** (OpenBMC pins this version).
* Ubuntu 24.04's `libgpiod-dev` package is **2.x**. Its functions have
  different names and the library file is different (`libgpiod.so.3`
  instead of `.so.2`), so code built against it won't run on the board.
* So we build version 1.6.5 for ARM, once, into a private folder
  (`~/bbb-gpio/sysroot`), and build it **into** our program, so nothing
  extra is needed on the board.

### 5b. Download and check the source

```sh
wget https://mirrors.edge.kernel.org/pub/software/libs/libgpiod/libgpiod-1.6.5.tar.xz
sha256sum libgpiod-1.6.5.tar.xz
```

* `wget` downloads libgpiod's official release from kernel.org.
* `sha256sum` computes the file's fingerprint (checksum). It must be:

  ```
  ae280f697bf035a1fb780c9972e5c81d0d2712b7ab6124fb3fba24619daa72bc  libgpiod-1.6.5.tar.xz
  ```

  A different value means the download is damaged or not the same file.
  Delete it and download again.

### 5c. Build and install it into a private folder

```sh
tar xf libgpiod-1.6.5.tar.xz
cd libgpiod-1.6.5
./configure --host=arm-linux-gnueabihf --prefix=$HOME/bbb-gpio/sysroot \
            --enable-static --disable-shared
make -j$(nproc)
make install
cd ..
```

| Command / option | Meaning |
| --- | --- |
| `tar xf libgpiod-1.6.5.tar.xz` | Unpack the archive (`x` extract, `f` from this file) into `libgpiod-1.6.5/` |
| `./configure` | libgpiod's setup script: checks the compiler and prepares the build files |
| `--host=arm-linux-gnueabihf` | **Build for the board**: makes `configure` use `arm-linux-gnueabihf-gcc` instead of the PC's `gcc` |
| `--prefix=$HOME/bbb-gpio/sysroot` | Where `make install` puts the result. A private folder, so nothing is mixed into your PC's own libraries. `$HOME` is your home folder. |
| `--enable-static` | Build `libgpiod.a`, a **static library**: code that gets copied into your program |
| `--disable-shared` | Don't build `libgpiod.so`, the version loaded at run time. We don't need it. |
| `\` at the end of a line | Continues the command on the next line |
| `make -j$(nproc)` | Compile. `$(nproc)` is your PC's number of processor cores, so `-j` uses all of them. |
| `make install` | Copy the results into the prefix folder. No `sudo` needed: it's your own folder. |
| `cd ..` | Back to `~/bbb-gpio` |

`configure` prints many `checking …` lines and ends without an error. The
command-line tools and language bindings are off by default, so only the
library is built.

Check the result:

```sh
ls sysroot/include sysroot/lib
```

Expected: `gpiod.h` in `include`, and `libgpiod.a` (plus `libgpiod.la` and
`pkgconfig`, which you can ignore) in `lib`.

You only do 5b and 5c **once**. Later programs reuse `sysroot`.

### 5d. Compile the program

```sh
arm-linux-gnueabihf-gcc -Wall -Wextra -O2 -I sysroot/include \
    -o gpio-blink-gpiod gpio-blink-gpiod.c -L sysroot/lib -l:libgpiod.a
```

| Part | Meaning |
| --- | --- |
| `-I sysroot/include` | Also look for header files here, so `#include <gpiod.h>` finds libgpiod 1.6.5's header |
| `-o gpio-blink-gpiod gpio-blink-gpiod.c` | Output name and source file |
| `-L sysroot/lib` | Also look for libraries here |
| `-l:libgpiod.a` | Link this exact file: the static libgpiod, built **into** the program. (`-lgpiod` without the `:` would also find it here, but the exact name makes it clear and avoids picking up any other copy.) |

The `-l` part goes **after** the source file. The linker only pulls in
library code that something before it needs.

The result uses libgpiod's code built in, and the **board's** C library at
run time. Check it with `file gpio-blink-gpiod`, as in 4b.

### 5e. Copy it to the board

```sh
scp gpio-blink-gpiod root@evb-beaglebone.local:
```

---

## 6. Run them on the board

On the board (serial console or SSH):

```sh
cd ~
./gpio-blink-uapi
./gpio-blink-gpiod
```

* `./` means "the program in this folder". The board doesn't look for
  programs in your home folder unless you say so.
* Expected output, with USR3 blinking **5 times** (on 0.5 s, off 0.5 s):

  ```
  found "[usr3 led]": /dev/gpiochip0 line 24
  done
  ```

  The libgpiod version prints `gpiochip0` without `/dev/`. The chip number
  may differ on your board (see the
  [LED guide, section 2a](turn-on-led-guide.md#2a-list-the-gpio-controllers)).

**Options** (the same for both programs, all optional, in this order):

```sh
./gpio-blink-uapi "[usr0 led]" 10 100
#                  │            │  └─ half-period in ms: 100 ms on, 100 ms off
#                  │            └──── blink 10 times
#                  └───────────────── line name, in quotes because of the [ ] and space
```

**See it holding the line.** While it's blinking, in a second SSH session:

```sh
gpioinfo | grep usr3
```

The owner shows `"gpio-blink-uapi"` (or `"gpio-blink-gpiod"`) with `output`
and `[used]`, **for the whole run**. It doesn't flip back to `unused input`
between blinks, which is the difference from calling `gpioset` repeatedly.

**Stopping early:** press **Ctrl-C**. The program ends, the kernel releases
the line, and on this chip it becomes an input, so the LED goes off.

---

## 7. How the code works

Both programs follow the same four steps. The comments in the source files
explain every line. Here are the key calls side by side.

| Step | Path A: `<linux/gpio.h>` | Path B: `<gpiod.h>` (libgpiod 1.6) |
| --- | --- | --- |
| 1. Find the line by name | Open `/dev/gpiochip0`, `1`, `2`…; ask each chip how many lines it has (`GPIO_GET_CHIPINFO_IOCTL`); ask each line its name (`GPIO_V2_GET_LINEINFO_IOCTL`) | `gpiod_line_find("[usr3 led]")` |
| 2. Reserve it as an output, starting low | Fill in a `struct gpio_v2_line_request` (line number, owner name, `GPIO_V2_LINE_FLAG_OUTPUT`, starting value 0) and call `ioctl(chip_fd, GPIO_V2_GET_LINE_IOCTL, &req)`. The kernel returns the line handle in `req.fd`. | `gpiod_line_request_output(line, "gpio-blink-gpiod", 0)` |
| 3. Change the value (while holding it) | `struct gpio_v2_line_values {.mask = 1, .bits = 0 or 1}` and `ioctl(req.fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &vals)` | `gpiod_line_set_value(line, 1)` / `(line, 0)` |
| 4. Release | `close(req.fd)` | `gpiod_line_release(line)` and `gpiod_line_close_chip(line)` |

Notes:
* **Glitch-free start.** The starting value is part of the request in both
  cases, so the kernel driver sets the value first and only then switches
  the pin to output.
* **The holding is what matters.** Between steps 2 and 4, the line belongs to
  the program and stays an output. Changing the value is one register write.
* **Why Path A zeroes every structure first (`memset(…, 0, …)`).** The kernel
  rejects requests whose reserved `padding` fields aren't zero.
* **Path B uses the older kernel interface underneath.** libgpiod 1.6 uses
  the kernel's "v1" GPIO calls, while Path A uses "v2". Both are enabled in
  our kernel, and the result is the same.
* **Which to use?** For programs that will become part of the OpenBMC image,
  prefer **Path B**: it's how OpenBMC's own programs are written, and the
  library is already in the image. Path A is handy for small standalone tools
  with no dependencies.
* More background: the LED guide's
  [section 6](turn-on-led-guide.md#6-what-happens-underneath) explains the
  layers from a program down to the pin.

---

## 8. Checking a program before you copy it

```sh
file gpio-blink-gpiod
arm-linux-gnueabihf-readelf -d gpio-blink-gpiod | grep NEEDED
arm-linux-gnueabihf-objdump -T gpio-blink-gpiod | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1
```

| Command | What it tells you | Expected |
| --- | --- | --- |
| `file` | Processor and format | `ARM, EABI5`, `interpreter /lib/ld-linux-armhf.so.3` |
| `readelf -d … \| grep NEEDED` | Which shared libraries the program needs on the board | Only `libc.so.6` and `ld-linux-armhf.so.3`. These are on every image. Path B has **no** `libgpiod.so` line, because libgpiod is built in. |
| `objdump -T … \| grep GLIBC_ … \| tail -1` | The newest C library version it needs | At most the board's **2.43**. Ubuntu 24.04 gave `GLIBC_2.38`. |

Optional: run `arm-linux-gnueabihf-strip gpio-blink-gpiod` to remove
debugging information and make the file smaller. It still works the same.

---

## 9. Troubleshooting

| Message (on the board) | Cause | Fix |
| --- | --- | --- |
| `cannot execute: required file not found`, `No such file or directory` or `Exec format error`, although the file is there | Built for the wrong processor, or needs a loader the board doesn't have | Check with `file` (section 8): it must say ARM and `ld-linux-armhf.so.3` |
| `Permission denied` | The file isn't marked as executable | `chmod +x gpio-blink-uapi` on the board |
| `version 'GLIBC_2.xx' not found` | Built with a C library newer than the board's 2.43 (e.g. on a much newer Ubuntu) | Build on an older Ubuntu, or add `-static` to the compile command, which puts the C library into the program (about 400 KB) |
| `no GPIO line named "…" found` | Name typed differently | The exact names are listed by `gpioinfo`. Quote names containing spaces or `[ ]`. |
| `cannot request … Device or resource busy` | Another program holds the line, e.g. a `gpioset` still running | `gpioinfo \| grep usr3` shows the owner. Stop it first. |
| LED doesn't change, but no error | Pin not in GPIO mode | Check the pin mux, as in the [LED guide, section 3](turn-on-led-guide.md#3-step-2-check-the-pin-mux) |
| (PC) `configure: error: C compiler cannot create executables` | Cross-compiler not installed | `sudo apt install gcc-arm-linux-gnueabihf` |
| (PC) `fatal error: gpiod.h: No such file or directory` | `-I sysroot/include` missing, or not in `~/bbb-gpio` | Run the command from `~/bbb-gpio`, as written in 5d |
| (PC) `undefined reference to 'gpiod_line_find'` | `-l:libgpiod.a` missing, or placed before the `.c` file | Put `-L sysroot/lib -l:libgpiod.a` at the end, as in 5d |

---

## 10. What comes next

* **The Yocto SDK.** Yocto can produce a cross-compiler kit made from the
  same build as the image (`bitbake obmc-phosphor-image -c populate_sdk`),
  with libgpiod 1.6.5, libi2c and the exact glibc already included. Then
  Path B needs no separate libgpiod build. It's planned for the next image
  build.
* **Into the image.** When a program should ship, it becomes a small recipe in
  `meta-evb-beaglebone` (`DEPENDS += "libgpiod"`), usually with a systemd
  service that starts it at boot.
* **The same approach works for I2C, SPI, UART and PWM programs:**
  * Path A style uses the kernel headers `<linux/i2c-dev.h>`,
    `<linux/spi/spidev.h>` and `<termios.h>`.
  * Path B style uses libraries such as **libi2c**, built for ARM the same way
    as libgpiod in section 5.
