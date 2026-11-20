# Cross-compile a GPIO program (Rust)

This is the **Rust version** of
[`cross-compile-a-gpio-program.md`](cross-compile-a-gpio-program.md) (C) and
[`cross-compile-a-gpio-program_cpp.md`](cross-compile-a-gpio-program_cpp.md)
(C++). It builds two Rust programs that blink a GPIO line, on your **Ubuntu
PC**, for the BeagleBone's ARM processor, and copies them to the board with
`scp`. Our OpenBMC image has no compiler of its own.

**Rust in one paragraph.** Rust is a compiled language like C and C++: it
produces ordinary machine code, with no interpreter. Its compiler also
**checks memory safety**: it refuses to build code that could use memory
after it's freed, run past the end of an array, or let two threads change
the same data at once. That's why it's increasingly used for low-level code;
the Linux kernel has accepted drivers written in Rust since 6.1. Code that
the compiler can't check (such as calling the kernel directly) has to be
marked **`unsafe`**, which you'll see in Path A.

| | Path A: `gpio-blink-uapi-rs` | Path B: `gpio-blink-gpiocdev-rs` |
| --- | --- | --- |
| Talks to the kernel through | The kernel's GPIO interface (`<linux/gpio.h>`, "v2") **directly**: its structures re-declared in Rust, calls through the `libc` crate | **gpiocdev**, a GPIO library written in Rust (it uses the same kernel interface underneath) |
| Like which C path | C Path A | C Path B, but with a Rust library instead of libgpiod |
| `unsafe` code | Yes, a few clearly marked lines | None in our program |
| Program size (stripped) | About 340 KB | About 400 KB |

In Rust, libraries are called **crates**, and **cargo** is Rust's build tool
and package manager. It downloads the crates a project needs from
[crates.io](https://crates.io), Rust's public package site.

**Why not libgpiod?** A Rust crate for libgpiod exists, but it's written for
**libgpiod 2.x**, and our board has 1.6.5. gpiocdev doesn't need libgpiod at
all, so the version question never comes up.

Both programs:
1. find a GPIO line **by its name** (default `[usr3 led]`, the USR3 LED);
2. **reserve it once** as an output, starting low;
3. blink it, then release it when finished.

Because the line is held the whole time, it **never falls back to an input**
between "on" and "off" (see the
[LED guide](turn-on-led-guide.md#4d-important-the-pin-is-only-yours-while-gpioset-runs)).

The project is in [`cross-compile-gpio_rust/`](cross-compile-gpio_rust/):

```
cross-compile-gpio_rust/
├── Cargo.toml                     project description: name, crates used, programs
├── Cargo.lock                     exact crate versions (gpiocdev 0.8.0, libc 0.2.191 …)
├── .cargo/config.toml             which linker to use for the board
├── .gitignore                     keeps the build folder (target/) out of git
└── src/bin/
    ├── gpio-blink-uapi-rs.rs      Path A
    └── gpio-blink-gpiocdev-rs.rs  Path B
```

> **What was tested, and how.**
> * **The build:** both programs built with **Rust 1.97.0** on **Ubuntu
>   24.04**, using the commands in sections 2–5. (Installing rustup itself,
>   step 2a, wasn't re-run: it was already installed.)
> * **Path A's structures:** their sizes and ioctl codes were compared with
>   the C header `<linux/gpio.h>` for 32-bit ARM, and they're identical. The
>   compiler also checks the sizes on every build.
> * **Against the board's C library:** both programs were run against the C
>   library copied from our released image (glibc 2.43), in an ARM emulator
>   (`qemu-arm`). They start, search for the line, and report correctly when
>   it isn't there (the emulator has no GPIO hardware).
> * **Path A's logic:** run with the kernel's GPIO calls faked out. It found
>   the line on the second chip, requested it as an output starting low, and
>   switched it high and low the right number of times, with the right timing.
>   A faked "busy" line produced the error
>   `cannot request /dev/gpiochip1 line 24: Device or resource busy (os error 16)`.
> * **Not yet:** running either program on the real board.

---

## Contents

1. [How cross-compiling Rust works](#1-how-cross-compiling-rust-works)
2. [One-time setup on Ubuntu](#2-one-time-setup-on-ubuntu)
3. [Get the project](#3-get-the-project)
4. [Build both programs](#4-build-both-programs)
5. [Copy them to the board](#5-copy-them-to-the-board)
6. [Run them on the board](#6-run-them-on-the-board)
7. [How the code works](#7-how-the-code-works)
8. [Checking a program before you copy it](#8-checking-a-program-before-you-copy-it)
9. [Troubleshooting](#9-troubleshooting)
10. [What comes next](#10-what-comes-next)

---

## 1. How cross-compiling Rust works

```
   Ubuntu PC (x86-64)                                      BeagleBone (ARM)
 ┌──────────────────────────────────────────────┐       ┌───────────────────────────────┐
 │ src/bin/*.rs  (your Rust source)             │       │                               │
 │       │                                      │       │ /home/root/gpio-blink-uapi-rs │
 │       ▼                                      │  scp  │       │                       │
 │ cargo build --target armv7-…-gnueabihf       │──────►│       ▼ runs with the board's │
 │   rustc: Rust source → ARM machine code      │       │   C library (glibc 2.43)      │
 │   arm-linux-gnueabihf-gcc: links it together │       │   and kernel                  │
 └──────────────────────────────────────────────┘       └───────────────────────────────┘
```

* **The target name** `armv7-unknown-linux-gnueabihf` describes the board:
  * `armv7`: the ARMv7 processor (Cortex-A8);
  * `unknown`: no particular vendor;
  * `linux-gnueabihf`: Linux, the GNU C library (glibc), hard-float.

  That's the same target as the C cross-compiler `arm-linux-gnueabihf-gcc`
  (see the C guide's
  [section 1](cross-compile-a-gpio-program.md#1-how-cross-compiling-works)).
* **Rust's compiler can already produce ARM code.** What you add is Rust's
  **standard library built for ARM** (`rustup target add …`, section 2c).
* **Linking needs an ARM C toolchain.** The last build step combines Rust's
  code with the board's C library. Rust hands that to a C linker, so we tell
  cargo to use `arm-linux-gnueabihf-gcc` (in `.cargo/config.toml`).
* **What the board needs at run time:** only the C library (`libc.so.6`),
  `libgcc_s.so.1` and the loader, all in our image. Rust's own standard
  library and the crates are **built into** the program. That's why Rust
  programs are bigger than the C ones.
* **C library versions:** as in C, a program built against an older glibc
  runs on a newer one. These programs need at most **GLIBC_2.34**, and the
  board has 2.43.

---

## 2. One-time setup on Ubuntu

### 2a. Install Rust with rustup

Rust's official installer is **rustup**. Ubuntu also has `rustc` and `cargo`
packages, but those can't add the ARM standard library. rustup can, and it
keeps Rust up to date.

```sh
sudo apt update
sudo apt install curl gcc-arm-linux-gnueabihf wget file
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

| Part | Meaning |
| --- | --- |
| `curl` | Downloads files. Here it fetches rustup's install script. |
| `gcc-arm-linux-gnueabihf` | The C cross-compiler, used by cargo **only to link** the final ARM program (section 1) |
| `wget` | Downloads the project files (section 3) |
| `file` | Tells you what kind of program a file is (section 8) |
| `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs` | Download the installer from rust-lang.org's official address, over HTTPS only (`--proto '=https'`), with modern encryption (`--tlsv1.2`). `-s` = no progress bar, `S` = still show errors, `f` = fail on HTTP errors. |
| `\| sh` | Run the downloaded installer script |

The installer asks a question. Press **Enter** for **1) Proceed with standard
installation**. It installs into your home folder (`~/.cargo` and
`~/.rustup`), with no `sudo`.

When it finishes, load Rust into the current terminal (new terminals do this
automatically):

```sh
. "$HOME/.cargo/env"
```

The leading `.` means "run this file in the current shell", so the `PATH`
change takes effect here. Then check:

```sh
rustc --version
cargo --version
```

Both print a version, e.g. `rustc 1.97.0 (…)`. The crates used here need at
least Rust 1.68, so any recent version is fine.

### 2b. Already have Rust?

Run `rustup update` to get the latest stable version, and skip to 2c.

### 2c. Add the ARM standard library

```sh
rustup target add armv7-unknown-linux-gnueabihf
```

This downloads Rust's standard library pre-built for the board's target
(section 1). Do it once. `rustup target list --installed` shows what you have.

---

## 3. Get the project

Make the folder layout cargo expects, and download the files into it:

```sh
mkdir -p ~/bbb-gpio-rust/src/bin ~/bbb-gpio-rust/.cargo
cd ~/bbb-gpio-rust
BASE=https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/cross-compile-gpio_rust
wget -O Cargo.toml                     $BASE/Cargo.toml
wget -O Cargo.lock                     $BASE/Cargo.lock
wget -O .cargo/config.toml             $BASE/.cargo/config.toml
wget -O src/bin/gpio-blink-uapi-rs.rs     $BASE/src/bin/gpio-blink-uapi-rs.rs
wget -O src/bin/gpio-blink-gpiocdev-rs.rs $BASE/src/bin/gpio-blink-gpiocdev-rs.rs
```

| Part | Meaning |
| --- | --- |
| `mkdir -p … src/bin … .cargo` | Create the project folder with its `src/bin` and `.cargo` subfolders. `-p` creates parent folders too and doesn't complain if they exist. |
| `BASE=…` | A shell variable holding the common start of the address, so the lines below stay short. `$BASE` is replaced by its value. |
| `wget -O <file> <address>` | Download, saving under this exact name (`-O`), so each file lands in the right subfolder |

`raw.githubusercontent.com` serves the repository's files as plain text. If
you have the repository cloned, copy the whole `beaglebone/cross-compile-gpio_rust/`
folder instead (including the hidden `.cargo` folder).

**All the commands below are run in `~/bbb-gpio-rust` unless they say
otherwise.**

### What's in the project files

**`Cargo.toml`**: the project description, in the TOML settings format:

```toml
[package]
name = "gpio-blink-rust"         # project name
version = "0.1.0"
edition = "2021"                 # which edition (version of the language rules) to use
license = "Apache-2.0"

[dependencies]                   # crates to download from crates.io
gpiocdev = "0.8"                 # Path B: GPIO library written in Rust
libc = "0.2"                     # Path A: raw C functions open(), ioctl(), close()

[[bin]]                          # a program to build ([[ ]] = one of several)
name = "gpio-blink-uapi-rs"      #   the program's file name
path = "src/bin/gpio-blink-uapi-rs.rs"

[[bin]]
name = "gpio-blink-gpiocdev-rs"
path = "src/bin/gpio-blink-gpiocdev-rs.rs"

[profile.release]                # settings for --release builds
strip = true                     # remove debugging information: smaller program
```

* `"0.8"` means "the newest 0.8.x".
* **`Cargo.lock`** records the **exact** versions that were tested: gpiocdev
  0.8.0, gpiocdev-uapi 0.7.0 and libc 0.2.191, plus their own dependencies.
  Building with `--locked` (section 4) uses exactly those.

**`.cargo/config.toml`**: cargo's settings for this project:

```toml
[target.armv7-unknown-linux-gnueabihf]   # when building for the board ...
linker = "arm-linux-gnueabihf-gcc"       # ... link with the ARM C cross-compiler
```

Without it, cargo would link with the PC's normal `cc`, which can't produce
ARM programs (see [Troubleshooting](#9-troubleshooting)).

---

## 4. Build both programs

```sh
cargo build --release --locked --target armv7-unknown-linux-gnueabihf
```

| Part | Meaning |
| --- | --- |
| `cargo build` | Download the crates (the first time only), compile them and our programs |
| `--release` | Optimised build, with `strip = true` from `Cargo.toml`. Without it you get a slower debug build in `target/…/debug/`. |
| `--locked` | Use exactly the versions in `Cargo.lock`. If something would need to change, stop with an error instead of silently using newer crates. |
| `--target armv7-unknown-linux-gnueabihf` | Build for the board (section 1) |

The first build downloads about a dozen small crates and takes a minute.
Later builds only recompile what changed. To build just one program, add
`--bin gpio-blink-uapi-rs` (or `--bin gpio-blink-gpiocdev-rs`).

The results are in **`target/armv7-unknown-linux-gnueabihf/release/`**:

```sh
ls -l target/armv7-unknown-linux-gnueabihf/release/gpio-blink-*
file target/armv7-unknown-linux-gnueabihf/release/gpio-blink-uapi-rs
```

`file` must say `ELF 32-bit LSB pie executable, ARM, EABI5 … interpreter
/lib/ld-linux-armhf.so.3`. (Ignore the `.d` files next to the programs: they
record build dependencies.)

---

## 5. Copy them to the board

```sh
scp target/armv7-unknown-linux-gnueabihf/release/gpio-blink-uapi-rs \
    target/armv7-unknown-linux-gnueabihf/release/gpio-blink-gpiocdev-rs \
    root@evb-beaglebone.local:
```

`scp` copies both files. The final `:` with nothing after it means the
board's home folder for `root`, `/home/root`. Run this on the **PC**.

---

## 6. Run them on the board

On the board (serial console or SSH):

```sh
cd ~
./gpio-blink-uapi-rs
./gpio-blink-gpiocdev-rs
```

Expected output, with USR3 blinking **5 times** (on 0.5 s, off 0.5 s):

```
found "[usr3 led]": /dev/gpiochip0 line 24
done
```

The chip number may differ on your board (see the
[LED guide, section 2a](turn-on-led-guide.md#2a-list-the-gpio-controllers)).

**Options** (the same for both programs, all optional, in this order):

```sh
./gpio-blink-uapi-rs "[usr0 led]" 10 100
#                     │            │  └─ half-period in ms: 100 ms on, 100 ms off
#                     │            └──── blink 10 times
#                     └───────────────── line name, in quotes because of the [ ] and space
```

**See it holding the line.** While it's blinking, in a second SSH session:

```sh
gpioinfo | grep usr3
```

The owner shows `"gpio-blink-uapi-rs"` (or `"gpio-blink-gpiocdev-rs"`) with
`output` and `[used]`, **for the whole run**.

**Stopping early:** press **Ctrl-C**. The program ends, the kernel releases
the line, and on this chip it becomes an input, so the LED goes off.

---

## 7. How the code works

### 7a. Path B: gpiocdev (the short one)

```rust
use gpiocdev::line::Value;                       // bring `Value` (Active/Inactive) into scope
use std::{env, thread, time::Duration};          // standard library parts we use

fn run() -> Result<(), Box<dyn std::error::Error>> {   // returns OK, or any kind of error
    let args: Vec<String> = env::args().collect();     // command-line arguments as a list
    let name = args.get(1).map(String::as_str).unwrap_or("[usr3 led]");
    let count: u32 = args.get(2).map(|s| s.parse()).transpose()?.unwrap_or(5);
    let half = Duration::from_millis(args.get(3).map(|s| s.parse()).transpose()?.unwrap_or(500));

    let found = gpiocdev::find_named_line(name)        // search every /dev/gpiochipN
        .ok_or_else(|| format!("no GPIO line named \"{name}\" found"))?;

    let req = gpiocdev::Request::builder()             // describe the request step by step:
        .with_found_line(&found)                       //   this line
        .with_consumer("gpio-blink-gpiocdev-rs")       //   owner name shown by gpioinfo
        .as_output(Value::Inactive)                    //   output, starting low
        .request()?;                                   //   ask the kernel

    for _ in 0..count {                                // repeat `count` times
        req.set_lone_value(Value::Active)?;            // high
        thread::sleep(half);
        req.set_lone_value(Value::Inactive)?;          // low
        thread::sleep(half);
    }
    drop(req);                                         // release the line now
    println!("done");
    Ok(())
}
```

(The `println!` showing where the line was found is left out above.)

| Rust idea | Meaning |
| --- | --- |
| `use a::b::C;` | Make `C` from module `b` of crate `a` usable by its short name. `::` separates the levels, as in C++. |
| `let x = …;` | Create a variable. It can't be changed afterwards unless declared `let mut`. |
| `Result<…>` and `?` | Rust has no exceptions. A function returns either a success value or an error, and `?` means "if this is an error, return it from this function right now". `run()` returns all errors to `main()`, which prints `error: …` and exits with status 1. |
| `Option` and `.unwrap_or(default)` | A value that may be missing. `args.get(2)` is missing if you gave fewer arguments, and `unwrap_or(5)` uses 5 then. |
| `s.parse()` | Text to number. If it fails (e.g. `abc`), the error is `invalid digit found in string`. |
| `\|s\| s.parse()` | A short unnamed function (a "closure") taking `s` |
| `format!("… {name} …")` | Build text, inserting the variable `name` |
| `Value::Active` / `Value::Inactive` | Logical on and off: named values instead of 1 and 0 |
| `Request::builder()…request()` | The **builder** style: set options one call at a time, then create the request |
| `drop(req)` | Destroy `req` now. Its clean-up code closes the line handle, so the kernel releases the line. Without `drop`, the same happens automatically at the end of the function. |

### 7b. Path A: the kernel interface directly

Path A does what the C Path A does, step by step. The C version gets the
kernel's structures from `<linux/gpio.h>`. Rust can't read C headers, so the
program **re-declares them**:

```rust
#[repr(C)]                       // lay this out in memory exactly as C would
struct GpioV2LineValues {
    bits: u64,                   // __aligned_u64 bits   (new levels)
    mask: u64,                   // __aligned_u64 mask   (which lines to change)
}
```

* `#[repr(C)]` tells the Rust compiler to use C's memory layout. By default,
  Rust may reorder fields.
* `u32`, `u64`, `i32` are Rust's fixed-size integers, the same as the
  kernel's `__u32`, `__aligned_u64` and `__s32`.
* `[u8; 32]` is an array of 32 bytes, like C's `char name[32]`.

**Safety checks the program adds.** A mistake in a copied structure would
make the kernel read the wrong memory. So:

```rust
const _: () = assert!(mem::size_of::<GpioV2LineRequest>() == 592);
```

The compiler checks each structure's size against the kernel's value on
every build, and **refuses to build** if one differs. I also compared the
sizes and the ioctl codes with the real C header for 32-bit ARM, and they
match.

**The ioctl codes** are built the same way as the kernel's `_IOWR(0xB4, 0x07,
struct gpio_v2_line_request)` macro (explained in the C guide):

```rust
const fn ioc(dir: u32, nr: u32, size: usize) -> u32 {
    (dir << 30) | ((size as u32) << 16) | (0xB4 << 8) | nr
}   // direction bits | structure size | 0xB4 = GPIO | command number
```

**`unsafe` blocks.** Calling `libc::open()` or `libc::ioctl()` hands raw
memory addresses to the kernel, which the Rust compiler can't check. Rust
requires those calls to sit in `unsafe { … }` blocks. Path A keeps them in a
few small helper functions (`ioctl()`, `open_rw()`, `zeroed()`), each with a
`// SAFETY:` comment saying why it's correct. The rest of the program is
ordinary, checked Rust.

**Automatic closing.** File descriptors are wrapped in Rust's standard
**`OwnedFd`** type, which closes the descriptor when it's dropped, like the
C++ `Fd` class. `drop(chip)` closes the chip; `drop(line)` releases the line.

| Step | Path A (`gpio-blink-uapi-rs.rs`) | Path B (`gpio-blink-gpiocdev-rs.rs`) |
| --- | --- | --- |
| 1. Find the line by name | `find_line()`: open `/dev/gpiochip0`, `1`…; `GPIO_GET_CHIPINFO_IOCTL` for the line count, `GPIO_V2_GET_LINEINFO_IOCTL` for each line's name | `gpiocdev::find_named_line(name)` |
| 2. Reserve it as an output, starting low | Fill in a zeroed `GpioV2LineRequest` and call `GPIO_V2_GET_LINE_IOCTL`. The kernel's line handle (`req.fd`) is wrapped in an `OwnedFd`. | `Request::builder()…as_output(Value::Inactive).request()` |
| 3. Change the value | `set_value()`: `GPIO_V2_LINE_SET_VALUES_IOCTL` | `req.set_lone_value(Value::Active)` |
| 4. Release | `drop(line)`, or automatically at the end | `drop(req)`, or automatically at the end |

**Which to use?** **Path B.** It's shorter and safe throughout, and gpiocdev
is maintained by people who keep up with the kernel interface. Path A is here
to show what happens underneath, and how Rust deals with C interfaces.

---

## 8. Checking a program before you copy it

```sh
P=target/armv7-unknown-linux-gnueabihf/release/gpio-blink-gpiocdev-rs
file $P
arm-linux-gnueabihf-readelf -d $P | grep NEEDED
arm-linux-gnueabihf-objdump -T $P | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1
```

`P=…` stores the path in a variable, so the three commands stay short.
(`arm-linux-gnueabihf-readelf` and `-objdump` come with the C cross-compiler
package.)

| Command | What it tells you | Expected |
| --- | --- | --- |
| `file` | Processor and format | `ARM, EABI5`, `interpreter /lib/ld-linux-armhf.so.3`, `stripped` |
| `readelf -d … \| grep NEEDED` | Shared libraries needed on the board | Only `libgcc_s.so.1`, `libc.so.6`, `ld-linux-armhf.so.3`. No Rust libraries: they're built in. |
| `objdump -T … GLIBC_` | Newest C library version needed | At most the board's **2.43**. Rust 1.97 gave `GLIBC_2.34`. |

---

## 9. Troubleshooting

| Message | Cause | Fix |
| --- | --- | --- |
| (PC) `cargo: command not found` | Rust not loaded in this terminal | `. "$HOME/.cargo/env"`, or open a new terminal |
| (PC) `can't find crate for 'std'` … `the 'armv7-unknown-linux-gnueabihf' target may not be installed` | ARM standard library missing | `rustup target add armv7-unknown-linux-gnueabihf` |
| (PC) `linking with 'cc' failed` … `file in wrong format` or `error adding symbols` | `.cargo/config.toml` missing, so the PC's normal linker was used | Download it again (section 3). The folder is `.cargo`, with a dot. |
| (PC) `linker 'arm-linux-gnueabihf-gcc' not found` | C cross-compiler not installed | `sudo apt install gcc-arm-linux-gnueabihf` |
| (PC) `the lock file … needs to be updated but --locked was passed` | `Cargo.lock` missing or edited | Download `Cargo.lock` again, or leave out `--locked` to let cargo choose versions |
| (PC) `failed to … download` crates | No internet access to crates.io | Check the network. Cargo needs `crates.io` and `static.crates.io`. |
| (board) `cannot execute: required file not found`, `No such file or directory` or `Exec format error`, although the file is there | Built for the PC instead of the board (`--target` missing) | Use the `target/armv7-unknown-linux-gnueabihf/release/` file, not `target/release/` |
| (board) `Permission denied` | File not marked as executable | `chmod +x gpio-blink-uapi-rs` |
| (board) `version 'GLIBC_2.xx' not found` | Built against a C library newer than the board's | Unlikely with these programs (they need 2.34). Ask if it happens. |
| (board) `error: no GPIO line named "…" found` | Name typed differently | `gpioinfo` lists the exact names. Quote names with spaces or `[ ]`. |
| (board) `error: cannot request … Device or resource busy (os error 16)` (Path A), or a "busy" message (Path B) | Another program holds the line, e.g. a running `gpioset` | `gpioinfo \| grep usr3` shows the owner. Stop it first. |
| (board) `error: invalid digit found in string` | The count or half-period isn't a number | Pass digits only, e.g. `10 100` |
| (board) LED doesn't change, but no error | Pin not in GPIO mode | Check the pin mux, as in the [LED guide, section 3](turn-on-led-guide.md#3-step-2-check-the-pin-mux) |

---

## 10. What comes next

* **Into the image.** Yocto supports Rust: OpenEmbedded-Core, which our build
  uses, includes the `cargo` and `rust` build classes, so a Rust program can
  be a recipe (`inherit cargo`) in our layer.
  * The first such build takes noticeably longer, because Yocto builds the
    Rust compiler itself from source.
  * Yocto also needs the exact crate versions listed in the recipe; the
    `cargo-update-recipe-crates` class generates that list from `Cargo.lock`.
* **Rust in OpenBMC.** OpenBMC's own programs are almost entirely **C++**.
  This repository's `meta-phosphor` layer has no Rust recipes. Rust is a good
  fit for your own add-on tools; for working on OpenBMC itself, C++ is the
  language to know.
* **Other buses from Rust:** crates exist for I2C and SPI on Linux
  (`i2cdev`, `spidev`) and for serial ports. Cross-compile them the same way:
  add the crate to `Cargo.toml` and build with the same `--target`.
