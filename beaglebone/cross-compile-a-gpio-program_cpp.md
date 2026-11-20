# Cross-compile a GPIO program (C++)

This is the **C++ version** of
[`cross-compile-a-gpio-program.md`](cross-compile-a-gpio-program.md). It
builds the same two blink programs, written in C++, on your **Ubuntu PC**
with a **cross-compiler** (a compiler that runs on the PC but produces
programs for the board's ARM processor), then copies them to the board with
`scp`. Our OpenBMC image has no compiler of its own.

| | Path A: `gpio-blink-uapi-cpp` | Path B: `gpio-blink-gpiod-cpp` |
| --- | --- | --- |
| Talks to the kernel through | `<linux/gpio.h>` directly (the kernel's GPIO interface, "v2"), wrapped in small C++ helpers | `<gpiod.hpp>`: **libgpiod 1.6's C++ interface**, the one OpenBMC's C++ programs use |
| Extra things to install on the PC | Nothing beyond the C++ cross-compiler | Build libgpiod 1.6.5 **with its C++ part** for ARM (a few minutes, once) |
| Program size | About 20 KB (14 KB after `strip`) | About 1.2 MB (55 KB after `strip`). libgpiod is built into it. |

Both programs:
1. find a GPIO line **by its name** (default `[usr3 led]`, the USR3 LED);
2. **reserve it once** as an output, starting low;
3. blink it, then release it when finished.

Because the line is held the whole time, it **never falls back to an input**
between "on" and "off" (see the
[LED guide](turn-on-led-guide.md#4d-important-the-pin-is-only-yours-while-gpioset-runs)).

The source files are in [`cross-compile-gpio_cpp/`](cross-compile-gpio_cpp/):
* [`gpio-blink-uapi.cpp`](cross-compile-gpio_cpp/gpio-blink-uapi.cpp)
* [`gpio-blink-gpiod.cpp`](cross-compile-gpio_cpp/gpio-blink-gpiod.cpp)

> **What was tested, and how.**
> * **The build commands:** every command in sections 2–5 was run on
>   **Ubuntu 24.04** exactly as written, and both programs built with no
>   warnings.
> * **Against the board's libraries:** both programs were run against the C
>   and C++ libraries copied from our released image (glibc 2.43, libstdc++
>   up to `GLIBCXX_3.4.35`), in an ARM emulator (`qemu-arm`). They start,
>   search for the line, and report correctly when it isn't there (the
>   emulator has no GPIO hardware).
> * **Path A's logic:** run with the kernel's GPIO calls faked out. It found
>   the line on the second chip, requested it as an output starting low, and
>   switched it high and low the right number of times, with the right timing.
>   A faked "busy" line produced the error
>   `cannot request /dev/gpiochip1 line 24: Device or resource busy`.
> * **Not yet:** running either program on the real board.

---

## Contents

1. [How cross-compiling C++ works](#1-how-cross-compiling-c-works)
2. [One-time setup on Ubuntu](#2-one-time-setup-on-ubuntu)
3. [Get the source files](#3-get-the-source-files)
4. [Path A: `<linux/gpio.h>`, no library](#4-path-a-linuxgpioh-no-library)
5. [Path B: libgpiod 1.6 C++ interface](#5-path-b-libgpiod-16-c-interface)
6. [Run them on the board](#6-run-them-on-the-board)
7. [How the code works](#7-how-the-code-works)
8. [Checking a program before you copy it](#8-checking-a-program-before-you-copy-it)
9. [Troubleshooting](#9-troubleshooting)
10. [What comes next](#10-what-comes-next)

---

## 1. How cross-compiling C++ works

```
   Ubuntu PC (x86-64)                                   BeagleBone (ARM)
 ┌────────────────────────────────────────┐          ┌────────────────────────────────┐
 │ gpio-blink-uapi.cpp  (your C++ source) │          │                                │
 │        │                               │          │ /home/root/gpio-blink-uapi-cpp │
 │        ▼                               │   scp    │        │                       │
 │ arm-linux-gnueabihf-g++ ──► program  ──┼─────────►│        ▼ runs with the board's │
 │   (C++ cross-compiler: runs on the PC, │          │   C++ library (libstdc++),     │
 │    produces 32-bit ARM code)           │          │   C library (glibc) and kernel │
 └────────────────────────────────────────┘          └────────────────────────────────┘
```

Everything in the C guide's
[section 1](cross-compile-a-gpio-program.md#1-how-cross-compiling-works)
applies: the same processor, the same 32-bit ARM hard-float target
(`arm-linux-gnueabihf`), and the same glibc rule. What's different for C++:

* **The compiler is `arm-linux-gnueabihf-g++`.** It's the same target as
  `arm-linux-gnueabihf-gcc`, but compiles C++ and links the C++ standard
  library.
* **C++ programs need two more libraries on the board at run time:**
  * **libstdc++**: the C++ standard library (`std::string`, `std::cout`,
    exceptions…);
  * **libgcc_s**: low-level helpers the compiler uses, e.g. for exceptions.
* **Our image has both**, because most of OpenBMC is written in C++.
* **The same version rule applies as for glibc.** A program built against an
  **older** libstdc++ runs on a **newer** one, not the other way round.
  * The board's libstdc++ supports up to `GLIBCXX_3.4.35`.
  * Ubuntu 24.04's compiler produced programs needing at most
    **`GLIBCXX_3.4.32`**, so they run.
  * Section 8 shows how to check.
* **libgpiod's C++ part isn't in our image.** Only the C library
  (`libgpiod.so.2`) is installed on the board. So Path B builds libgpiod's
  C++ part and puts it **into** the program.

---

## 2. One-time setup on Ubuntu

```sh
sudo apt update
sudo apt install g++-arm-linux-gnueabihf gcc-arm-linux-gnueabihf build-essential wget xz-utils file
```

| Package | What it gives you |
| --- | --- |
| `g++-arm-linux-gnueabihf` | The C++ cross-compiler `arm-linux-gnueabihf-g++`, and the ARM C++ standard library and headers (`<string>`, `<iostream>`…) |
| `gcc-arm-linux-gnueabihf` | The C cross-compiler, the ARM C library, and kernel headers such as `<linux/gpio.h>`. libgpiod's own source is C, so Path B needs it. (`g++-…` usually installs it too.) |
| `build-essential` | `make` and the PC's own compilers; libgpiod's build (Path B) needs `make` |
| `wget` | Downloads files from the web |
| `xz-utils` | Unpacks `.tar.xz` archives |
| `file` | Tells you what kind of program a file is (section 8) |

Check that the C++ cross-compiler works:

```sh
arm-linux-gnueabihf-g++ --version
```

It prints its version, e.g.
`arm-linux-gnueabihf-g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`.

Make a working folder for this guide. It's separate from the C guide's
`~/bbb-gpio`, so the two don't mix:

```sh
mkdir -p ~/bbb-gpio-cpp
cd ~/bbb-gpio-cpp
```

**All the commands below are run in `~/bbb-gpio-cpp` unless they say
otherwise.**

---

## 3. Get the source files

```sh
wget https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/cross-compile-gpio_cpp/gpio-blink-uapi.cpp
wget https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/cross-compile-gpio_cpp/gpio-blink-gpiod.cpp
```

`raw.githubusercontent.com` serves the repository's files as plain text. If
you have the repository cloned, copy them from its
`beaglebone/cross-compile-gpio_cpp/` folder instead.

---

## 4. Path A: `<linux/gpio.h>`, no library

### 4a. Compile

```sh
arm-linux-gnueabihf-g++ -std=c++17 -Wall -Wextra -O2 -o gpio-blink-uapi-cpp gpio-blink-uapi.cpp
```

| Part | Meaning |
| --- | --- |
| `arm-linux-gnueabihf-g++` | The C++ cross-compiler |
| `-std=c++17` | The C++ language version (C++17). The program uses `std::optional`, which needs at least 17. OpenBMC itself uses C++20 or newer; `-std=c++20` works here too. |
| `-Wall -Wextra` | Warnings about suspicious code. There should be none. |
| `-O2` | Normal optimisation |
| `-o gpio-blink-uapi-cpp` | Name of the program to produce |
| `gpio-blink-uapi.cpp` | The source file |

`<linux/gpio.h>` is a C header, but C++ can include it directly. It comes
with the cross-compiler packages, so no `-I` or `-l` is needed.

### 4b. Check it

```sh
file gpio-blink-uapi-cpp
```

Expected: `ELF 32-bit LSB pie executable, ARM, EABI5 … interpreter
/lib/ld-linux-armhf.so.3 …`. **ARM** is what matters.

### 4c. Copy it to the board

```sh
scp gpio-blink-uapi-cpp root@evb-beaglebone.local:
```

The `:` with nothing after it means the board's home folder for `root`,
`/home/root`. Run this on the **PC**.

---

## 5. Path B: libgpiod 1.6 C++ interface

### 5a. Why build libgpiod yourself?

* The board has **libgpiod 1.6.5**, but only its **C** part. Its **C++ part**
  (`libgpiodcxx`) isn't in our image.
* Ubuntu 24.04's `libgpiod-dev` is **2.x**, whose C++ interface is completely
  different (`gpiod::chip`, `gpiod::line_request`…). Code built against it
  won't run on the board.
* So we build version 1.6.5 **with the C++ part** for ARM, once, into a
  private folder (`~/bbb-gpio-cpp/sysroot`), and build it **into** our
  program.

### 5b. Download and check the source

```sh
wget https://mirrors.edge.kernel.org/pub/software/libs/libgpiod/libgpiod-1.6.5.tar.xz
sha256sum libgpiod-1.6.5.tar.xz
```

The checksum must be:

```
ae280f697bf035a1fb780c9972e5c81d0d2712b7ab6124fb3fba24619daa72bc  libgpiod-1.6.5.tar.xz
```

A different value means a damaged or different file. Delete it and download
again.

### 5c. Build and install it, with the C++ part

```sh
tar xf libgpiod-1.6.5.tar.xz
cd libgpiod-1.6.5
./configure --host=arm-linux-gnueabihf --prefix=$HOME/bbb-gpio-cpp/sysroot \
            --enable-static --disable-shared --enable-bindings-cxx
make -j$(nproc)
make install
cd ..
```

| Command / option | Meaning |
| --- | --- |
| `tar xf libgpiod-1.6.5.tar.xz` | Unpack the archive into `libgpiod-1.6.5/` |
| `./configure` | libgpiod's setup script: checks the compilers and prepares the build |
| `--host=arm-linux-gnueabihf` | **Build for the board**: use `arm-linux-gnueabihf-gcc` for the C part and `arm-linux-gnueabihf-g++` for the C++ part |
| `--prefix=$HOME/bbb-gpio-cpp/sysroot` | Where `make install` puts the result: a private folder, not your PC's own libraries |
| `--enable-static` | Build static libraries (`.a`): code that gets copied into your program |
| `--disable-shared` | Don't build the run-time `.so` versions |
| **`--enable-bindings-cxx`** | **Also build the C++ part**: `gpiod.hpp` and `libgpiodcxx.a`. (Libraries that expose one language's functions to another are called "bindings".) This is the only difference from the C guide. |
| `make -j$(nproc)` | Compile, using all your PC's processor cores |
| `make install` | Copy the results into the prefix folder (no `sudo`: it's your own folder) |
| `cd ..` | Back to `~/bbb-gpio-cpp` |

Check the result:

```sh
ls sysroot/include sysroot/lib
```

Expected:
* `include`: `gpiod.h` (C) and **`gpiod.hpp`** (C++);
* `lib`: `libgpiod.a` and **`libgpiodcxx.a`** (plus `.la` files and
  `pkgconfig`, which you can ignore).

You only do 5b and 5c **once**.

### 5d. Compile the program

```sh
arm-linux-gnueabihf-g++ -std=c++17 -Wall -Wextra -O2 -I sysroot/include \
    -o gpio-blink-gpiod-cpp gpio-blink-gpiod.cpp -L sysroot/lib -l:libgpiodcxx.a -l:libgpiod.a
```

| Part | Meaning |
| --- | --- |
| `-std=c++17` | C++ language version |
| `-I sysroot/include` | Also look for headers here, so `#include <gpiod.hpp>` finds libgpiod 1.6.5's |
| `-o gpio-blink-gpiod-cpp gpio-blink-gpiod.cpp` | Output name and source file |
| `-L sysroot/lib` | Also look for libraries here |
| `-l:libgpiodcxx.a -l:libgpiod.a` | Link both static libraries, **in this order**. The C++ part (`libgpiodcxx`) calls the C part (`libgpiod`), and the linker only resolves calls to libraries that come **later** on the line. Swapping them gives `undefined reference to 'gpiod_…'` errors. |

Check it with `file gpio-blink-gpiod-cpp`, as in 4b.

### 5e. Copy it to the board

```sh
scp gpio-blink-gpiod-cpp root@evb-beaglebone.local:
```

The unstripped program is about 1.2 MB, mostly debugging information. Use
`arm-linux-gnueabihf-strip gpio-blink-gpiod-cpp` first to make it about
55 KB (section 8).

---

## 6. Run them on the board

On the board (serial console or SSH):

```sh
cd ~
./gpio-blink-uapi-cpp
./gpio-blink-gpiod-cpp
```

Expected output, with USR3 blinking **5 times** (on 0.5 s, off 0.5 s):

```
found "[usr3 led]": /dev/gpiochip0 line 24
done
```

The libgpiod version prints `gpiochip0` without `/dev/`. The chip number may
differ on your board (see the
[LED guide, section 2a](turn-on-led-guide.md#2a-list-the-gpio-controllers)).

**Options** (the same for both programs, all optional, in this order):

```sh
./gpio-blink-uapi-cpp "[usr0 led]" 10 100
#                      │            │  └─ half-period in ms: 100 ms on, 100 ms off
#                      │            └──── blink 10 times
#                      └───────────────── line name, in quotes because of the [ ] and space
```

**See it holding the line.** While it's blinking, in a second SSH session:

```sh
gpioinfo | grep usr3
```

The owner shows `"gpio-blink-uapi-cpp"` (or `"gpio-blink-gpiod-cpp"`) with
`output` and `[used]`, **for the whole run**.

**Stopping early:** press **Ctrl-C**. The program ends, the kernel releases
the line, and on this chip it becomes an input, so the LED goes off.

---

## 7. How the code works

Both programs follow the same four steps as the C versions. The comments in
the source files explain every line.

| Step | Path A: `<linux/gpio.h>` in C++ | Path B: `<gpiod.hpp>` (libgpiod 1.6) |
| --- | --- | --- |
| 1. Find the line by name | `find_line()`: open `/dev/gpiochip0`, `1`…; ask each chip its line count (`GPIO_GET_CHIPINFO_IOCTL`) and each line its name (`GPIO_V2_GET_LINEINFO_IOCTL`). Returns `std::optional<FoundLine>`: empty if not found. | `gpiod::line line = gpiod::find_line(name);` An empty `line` (tested with `if (!line)`) means not found. |
| 2. Reserve it as an output, starting low | `request_output()` fills in `gpio_v2_line_request` and calls `ioctl(…, GPIO_V2_GET_LINE_IOCTL, …)`. The kernel's line handle comes back wrapped in an `Fd` object. | `line.request({"gpio-blink-gpiod-cpp", gpiod::line_request::DIRECTION_OUTPUT, 0}, 0);` The braces build a `gpiod::line_request`: owner name, direction, flags. The last `0` is the starting value. |
| 3. Change the value (while holding it) | `set_value(line, 1)`: `ioctl(…, GPIO_V2_LINE_SET_VALUES_IOCTL, …)` | `line.set_value(1);` |
| 4. Release | Automatic: the `Fd` object closes the handle when it goes out of scope | `line.release();`, and also automatic when `line` goes away |

What C++ changes compared with the C versions:

* **Automatic clean-up ("RAII").**
  * Path A's small `Fd` class owns a file descriptor and closes it in its
    destructor: the function C++ runs automatically when an object goes
    away. Whatever path the program takes out of a block (normal end, early
    `return`, or an error), the chip and line handles are closed. That
    releases the line.
  * libgpiod's `gpiod::line` and `gpiod::chip` do the same internally.
  * `Fd` can be **moved** but not **copied**, so exactly one object owns each
    descriptor and it's never closed twice.
* **Errors are exceptions, not return codes.**
  * Path A's `throw_errno()` turns a failed system call into a
    `std::system_error` with the system's message (e.g. "Device or resource
    busy").
  * libgpiod's C++ functions throw on failure.
  * Both programs catch everything in one `try … catch` in `main()` and print
    `error: …`.
* **Zeroing structures:** `gpio_v2_line_request req{};` (empty braces) sets
  every field to zero, the C++ equivalent of the C version's `memset()`. The
  kernel requires the reserved `padding` fields to be zero.
* **Waiting:** `std::this_thread::sleep_for(std::chrono::milliseconds(…))`
  instead of `usleep()` or `nanosleep()`.
* **Why the line stays glitch-free** is unchanged: the starting value is part
  of the request, and the line is held from step 2 to step 4.
* **Which to use?** For programs that will become part of the OpenBMC image,
  prefer **Path B**: libgpiod's C++ interface is what OpenBMC's C++ programs
  use. (When it's built into the image, the program uses the image's
  `libgpiodcxx` package instead of bundling it; see section 10.) Path A is handy for small tools
  with no dependencies.

---

## 8. Checking a program before you copy it

```sh
file gpio-blink-gpiod-cpp
arm-linux-gnueabihf-readelf -d gpio-blink-gpiod-cpp | grep NEEDED
arm-linux-gnueabihf-objdump -T gpio-blink-gpiod-cpp | grep -o 'GLIBC_[0-9.]*'   | sort -uV | tail -1
arm-linux-gnueabihf-objdump -T gpio-blink-gpiod-cpp | grep -o 'GLIBCXX_[0-9.]*' | sort -uV | tail -1
```

| Command | What it tells you | Expected |
| --- | --- | --- |
| `file` | Processor and format | `ARM, EABI5`, `interpreter /lib/ld-linux-armhf.so.3` |
| `readelf -d … \| grep NEEDED` | Shared libraries the program needs on the board | `libstdc++.so.6`, `libgcc_s.so.1`, `libc.so.6`, `ld-linux-armhf.so.3`. All are in our image. No `libgpiod…`: it's built in. |
| `objdump -T … GLIBC_` | Newest C library version needed | At most the board's **2.43**. Ubuntu 24.04 gave `GLIBC_2.38`. |
| `objdump -T … GLIBCXX_` | Newest C++ library version needed | At most the board's **`GLIBCXX_3.4.35`**. Ubuntu 24.04 gave `GLIBCXX_3.4.32`. |

**Make it smaller** (optional; it works the same):

```sh
arm-linux-gnueabihf-strip gpio-blink-gpiod-cpp
```

`strip` removes debugging information: 1.2 MB becomes about 55 KB, and Path
A's 20 KB becomes about 14 KB.

---

## 9. Troubleshooting

| Message | Cause | Fix |
| --- | --- | --- |
| (board) `cannot execute: required file not found`, `No such file or directory` or `Exec format error`, although the file is there | Built for the wrong processor, e.g. with the PC's own `g++` | Check with `file` (section 8): it must say ARM and `ld-linux-armhf.so.3` |
| (board) `Permission denied` | File not marked as executable | `chmod +x gpio-blink-uapi-cpp` |
| (board) `version 'GLIBCXX_3.4.xx' not found` or `version 'GLIBC_2.xx' not found` | Built with a compiler newer than the board's libraries (e.g. on a much newer Ubuntu) | Build on an older Ubuntu, or add `-static-libstdc++ -static-libgcc` (puts the C++ library into the program), or `-static` (puts everything in) |
| (board) `no GPIO line named "…" found` | Name typed differently | `gpioinfo` lists the exact names. Quote names with spaces or `[ ]`. |
| (board) `error: cannot request … Device or resource busy` (Path A) or `error: … Device or resource busy` (Path B) | Another program holds the line, e.g. a running `gpioset` | `gpioinfo \| grep usr3` shows the owner. Stop it first. |
| (board) `error: stol` | The count or half-period isn't a number | `std::stol` (string to long) couldn't read it. Pass digits only, e.g. `10 100`. |
| (board) LED doesn't change, but no error | Pin not in GPIO mode | Check the pin mux, as in the [LED guide, section 3](turn-on-led-guide.md#3-step-2-check-the-pin-mux) |
| (PC) `configure: error: C++ compiler cannot create executables` | C++ cross-compiler missing | `sudo apt install g++-arm-linux-gnueabihf` |
| (PC) `fatal error: gpiod.hpp: No such file or directory` | libgpiod built without `--enable-bindings-cxx`, or `-I sysroot/include` missing | Re-run 5c with `--enable-bindings-cxx` (it's fine to run it again in the same folder), and compile from `~/bbb-gpio-cpp` |
| (PC) `undefined reference to 'gpiod_…'` | `-l:libgpiod.a` missing, or listed before `-l:libgpiodcxx.a` | Use exactly `-L sysroot/lib -l:libgpiodcxx.a -l:libgpiod.a`, at the end of the line |
| (PC) `undefined reference to 'gpiod::…'` | `-l:libgpiodcxx.a` missing | As above |

---

## 10. What comes next

* **The Yocto SDK.** Yocto can produce a cross-compiler kit from the same
  build as the image (`bitbake obmc-phosphor-image -c populate_sdk`). It
  includes the exact C and C++ libraries, and libgpiod (its C++ part too, if
  the image includes it). Then Path B needs no separate libgpiod build. It's
  planned for the next image build.
* **Into the image.** OpenBMC's C++ programs are built with **Meson** and
  turned into recipes in a layer. A recipe for this program would contain:
  * `DEPENDS += "libgpiod"`;
  * usually a systemd service that starts the program at boot.

  libgpiod's Yocto recipe **already builds** the C++ part (its
  `PACKAGECONFIG` includes `cxx` by default). It puts it in a separate
  package, `libgpiodcxx`. Our image doesn't contain that package only because
  nothing in it uses it yet. Once a recipe's program links against it, Yocto
  adds `libgpiodcxx` to the image automatically.
* **The same approach works for I2C, SPI, UART and PWM in C++.** The kernel
  headers (`<linux/i2c-dev.h>`, `<linux/spi/spidev.h>`, `<termios.h>`) are
  plain C and work from C++ unchanged. Wrap the file descriptor in the same
  `Fd` class.
