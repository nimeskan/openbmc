# Hook up the identify and heartbeat LEDs (Rust stand-in)

This is the **Rust version** of
[`hook-up-identify-and-heartbeat-leds_cpp.md`](hook-up-identify-and-heartbeat-leds_cpp.md).
The result on the board is identical:

| LED | Shows | Driven by the OpenBMC LED group |
| --- | --- | --- |
| **USR3** | **Identify**: blinks once a second while identify is on (web UI switch or Redfish) | `enclosure_identify_blink` (and `enclosure_identify`) |
| **USR0** | **BMC booted**: a short flash once a second once OpenBMC is up | `bmc_booted` |

Only the stand-in program differs. It's written in Rust with **zbus** (a D-Bus
library written in Rust) and **gpiocdev** (the GPIO library from the
[Rust cross-compile guide](cross-compile-a-gpio-program_rust.md)). It has the
same bus name, the same D-Bus objects and the same LED configuration, so the
explanations in the C++ guide apply unchanged. This guide links to them
rather than repeating them.

> **Coming from the C++ version?** Do its
> [section 11 (remove everything)](hook-up-identify-and-heartbeat-leds_cpp.md#11-remove-everything-before-trying-the-rust-version)
> first. Both versions use the same D-Bus name and GPIO lines, so only one can
> run at a time.

> **What was tested, and how.**
> * **The build:** the program was cross-compiled with **Rust 1.97** on
>   **Ubuntu 24.04** using the commands in section 3, with the exact crate
>   versions in `Cargo.lock` (zbus 5.19.0, gpiocdev 0.8.0).
> * **Against the board's library:** it was run in an ARM emulator against the
>   C library copied from our image (glibc 2.43). It starts, and reports a
>   clear error when there's no GPIO or D-Bus.
> * **The D-Bus side:** a PC build of the same source was run with
>   `--dry-run` on a private test D-Bus. `busctl` showed the four LED objects
>   with the standard properties and types. Setting `DutyOn`, `Period` and
>   `State` exactly the way OpenBMC's LED manager does produced the right
>   on/off pattern and timing, a period change while blinking took effect, and
>   an invalid value was rejected.
> * **End to end on the PC:** see the
>   [C++ guide, section 6e](hook-up-identify-and-heartbeat-leds_cpp.md#6e-what-was-tested-end-to-end-on-a-pc).
>   The Rust stand-in was tested the same way.
> * **Not yet:** running on the real board.

---

## Contents

1. [How it fits together](#1-how-it-fits-together)
2. [The files](#2-the-files)
3. [Build on Ubuntu](#3-build-on-ubuntu)
4. [Install on the board](#4-install-on-the-board)
5. [Check every layer](#5-check-every-layer)
6. [How the Rust program works](#6-how-the-rust-program-works)
7. [Troubleshooting](#7-troubleshooting)
8. [Remove everything](#8-remove-everything)

---

## 1. How it fits together

Exactly as in the C++ guide:
* [Why a stand-in is needed](hook-up-identify-and-heartbeat-leds_cpp.md#1-why-a-stand-in-is-needed)
* [How the pieces fit together](hook-up-identify-and-heartbeat-leds_cpp.md#2-how-the-pieces-fit-together)

In short:
* OpenBMC's LED manager reads `/etc/phosphor-led-manager/led-group-config.json`.
* For each LED, it asks the object mapper which program serves the LED's
  D-Bus object under `/xyz/openbmc_project/led/physical/`, then sets that
  object's `State`, `DutyOn` and `Period` properties.
* The stand-in publishes those objects as the D-Bus service
  `xyz.openbmc_project.LED.GpioStandIn`, and drives the GPIO lines.

| D-Bus object (under `/xyz/openbmc_project/led/physical/`) | LED | GPIO line name |
| --- | --- | --- |
| `beaglebone_heartbeat_green` | USR0 | `[usr0 led]` |
| `beaglebone_mmc0_green` | USR1 | `[usr1 led]` |
| `beaglebone_usr2_green` | USR2 | `[usr2 led]` |
| `beaglebone_usr3_green` | USR3 | `[usr3 led]` |

---

## 2. The files

All in [`led-standin_rust/`](led-standin_rust/):

| File | What it is | Where it goes on the board |
| --- | --- | --- |
| [`Cargo.toml`](led-standin_rust/Cargo.toml) | Project description: name, crates used | (PC only) |
| [`Cargo.lock`](led-standin_rust/Cargo.lock) | Exact crate versions that were tested | (PC only) |
| [`.cargo/config.toml`](led-standin_rust/.cargo/config.toml) | Link with the ARM C cross-compiler when building for the board | (PC only) |
| [`src/main.rs`](led-standin_rust/src/main.rs) | The stand-in program's source | Compiled on the PC; the program goes to `/usr/local/bin/bbb-led-standin-rs` |
| [`led-group-config.json`](led-standin_rust/led-group-config.json) | Which LEDs belong to which LED group (identical to the C++ version) | `/etc/phosphor-led-manager/led-group-config.json` |
| [`bbb-led-standin-rs.service`](led-standin_rust/bbb-led-standin-rs.service) | systemd unit that starts the stand-in at boot | `/etc/systemd/system/bbb-led-standin-rs.service` |

* The configuration is explained in the
  [C++ guide, section 8a](hook-up-identify-and-heartbeat-leds_cpp.md#8a-the-led-configuration).
* The service file is explained in
  [section 8b](hook-up-identify-and-heartbeat-leds_cpp.md#8b-the-service-file).
  The Rust one differs only in its description and `ExecStart=/usr/local/bin/bbb-led-standin-rs`.

`Cargo.toml`:

```toml
[package]
name = "bbb-led-standin-rs"      # also the program's file name
version = "0.1.0"
edition = "2021"
license = "Apache-2.0"

[dependencies]
gpiocdev = "0.8"                 # GPIO (kernel GPIO interface v2)
zbus = { version = "5", default-features = false, features = ["blocking-api", "async-io"] }

[profile.release]
strip = true                     # remove debugging information: smaller program
```

`zbus` options:
* `default-features = false` switches off zbus's optional extras.
* `features = [...]` switches two back on:
  * **`blocking-api`**: the simple, non-`async` interface this program uses;
  * **`async-io`**: the small built-in engine zbus uses internally to handle
    D-Bus messages on its own thread.

---

## 3. Build on Ubuntu

### 3a. Rust and the ARM target

If you followed the [Rust cross-compile guide](cross-compile-a-gpio-program_rust.md)
section 2, you already have everything: skip to 3b. Otherwise:

```sh
sudo apt update
sudo apt install curl gcc-arm-linux-gnueabihf wget file
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   # press Enter for the standard install
. "$HOME/.cargo/env"
rustup target add armv7-unknown-linux-gnueabihf
```

What each command does is explained in the
[Rust cross-compile guide, section 2](cross-compile-a-gpio-program_rust.md#2-one-time-setup-on-ubuntu).

Unlike the C++ version, **nothing else is needed**: zbus speaks the D-Bus
protocol itself, so there's no libsystemd to copy from the board.

### 3b. Get the project

```sh
mkdir -p ~/bbb-led-rust/src ~/bbb-led-rust/.cargo
cd ~/bbb-led-rust
BASE=https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/led-standin_rust
wget -O Cargo.toml                 $BASE/Cargo.toml
wget -O Cargo.lock                 $BASE/Cargo.lock
wget -O .cargo/config.toml         $BASE/.cargo/config.toml
wget -O src/main.rs                $BASE/src/main.rs
wget -O led-group-config.json      $BASE/led-group-config.json
wget -O bbb-led-standin-rs.service $BASE/bbb-led-standin-rs.service
```

`wget -O <file>` saves each download under that exact name, so the files land
in the folders cargo expects. **All the commands below are run in
`~/bbb-led-rust`.**

### 3c. Build

```sh
cargo build --release --locked --target armv7-unknown-linux-gnueabihf
```

| Part | Meaning |
| --- | --- |
| `--release` | Optimised build; stripped (from `Cargo.toml`) |
| `--locked` | Use exactly the crate versions in `Cargo.lock` |
| `--target armv7-unknown-linux-gnueabihf` | Build for the board |

* The first build downloads about 90 small crates (zbus has many helpers)
  and takes a few minutes. Later builds take seconds.
* The result is `target/armv7-unknown-linux-gnueabihf/release/bbb-led-standin-rs`,
  about **2.1 MB**. That's larger than the C++ version's 63 KB, because Rust
  builds zbus and its own standard library into the program. On our board's
  eMMC, that's not a concern.

Check it:

```sh
P=target/armv7-unknown-linux-gnueabihf/release/bbb-led-standin-rs
file $P
arm-linux-gnueabihf-readelf -d $P | grep NEEDED
arm-linux-gnueabihf-objdump -T $P | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1
```

| Check | Expected |
| --- | --- |
| `file` | `ARM, EABI5`, `interpreter /lib/ld-linux-armhf.so.3`, `stripped` |
| `NEEDED` | Only `libgcc_s.so.1`, `libc.so.6`, `ld-linux-armhf.so.3` |
| newest `GLIBC_` | `GLIBC_2.39` or lower (the board has 2.43) |

### 3d. Copy the three files to the board

```sh
scp target/armv7-unknown-linux-gnueabihf/release/bbb-led-standin-rs \
    led-group-config.json bbb-led-standin-rs.service root@evb-beaglebone.local:
```

They land in `/home/root` on the board.

---

## 4. Install on the board

Run these **on the board**. They're the same steps as in the
[C++ guide, section 5](hook-up-identify-and-heartbeat-leds_cpp.md#5-install-on-the-board),
which explains every command, with the Rust file names.

### 4a. Dry run in the foreground (optional, recommended)

```sh
cd ~
chmod +x bbb-led-standin-rs
./bbb-led-standin-rs --dry-run
```

Expected:
* one line per LED, e.g. `beaglebone_usr3_green: Off` and
  `[dry-run] beaglebone_usr3_green = 0`;
* then `bbb-led-standin-rs: serving 4 LEDs as
  xyz.openbmc_project.LED.GpioStandIn (dry run: no GPIO)`.

From a second SSH session:

```sh
busctl tree xyz.openbmc_project.LED.GpioStandIn
busctl set-property xyz.openbmc_project.LED.GpioStandIn \
    /xyz/openbmc_project/led/physical/beaglebone_usr3_green \
    xyz.openbmc_project.Led.Physical State s xyz.openbmc_project.Led.Physical.Action.Blink
```

The first session prints `beaglebone_usr3_green: Blink (period 1000 ms, on 50 %)`
and alternating `= 1` / `= 0` lines. Set it back to `…Action.Off`, then press
**Ctrl-C** in the first session.

### 4b. Install

```sh
mkdir -p /usr/local/bin
install -m 0755 ~/bbb-led-standin-rs /usr/local/bin/bbb-led-standin-rs
mkdir -p /etc/phosphor-led-manager
install -m 0644 ~/led-group-config.json /etc/phosphor-led-manager/led-group-config.json
install -m 0644 ~/bbb-led-standin-rs.service /etc/systemd/system/bbb-led-standin-rs.service
```

### 4c. Start it, and at every boot

```sh
systemctl daemon-reload
systemctl enable --now bbb-led-standin-rs.service
systemctl status bbb-led-standin-rs.service
```

Expected: `Active: active (running)`.

### 4d. Restart the LED manager, and assert "BMC booted"

```sh
systemctl restart xyz.openbmc_project.LED.GroupManager.service
systemctl restart obmc-led-group-start@bmc_booted.service
```

Expected: **USR0 starts a short flash once a second.**

---

## 5. Check every layer

Use the checks in the
[C++ guide, section 6](hook-up-identify-and-heartbeat-leds_cpp.md#6-check-every-layer),
with two differences:

| Check | Rust version |
| --- | --- |
| `gpioinfo \| grep led` | Owner shows `"bbb-led-standin-rs"` |
| Service log | `journalctl -u bbb-led-standin-rs.service -b --no-pager \| tail` |

Everything else is identical:
* `mapper get-service …/beaglebone_usr3_green` →
  `xyz.openbmc_project.LED.GpioStandIn`;
* the LED groups in `busctl tree xyz.openbmc_project.LED.GroupManager`;
* asserting `enclosure_identify_blink` by hand;
* the web UI switch;
* the Redfish `PATCH` of `LocationIndicatorActive`;
* the reboot test.

---

## 6. How the Rust program works

The source is [`src/main.rs`](led-standin_rust/src/main.rs), about 270 lines,
commented throughout.

### 6a. Design: one D-Bus thread, one thread per LED

```
 zbus's own thread                         one worker thread per LED
 ┌───────────────────────────┐   shared    ┌──────────────────────────────┐
 │ answers D-Bus calls:      │  settings   │ holds the GPIO line          │
 │ Get/Set State, DutyOn,    │────────────►│ On/Off: set level, wait      │
 │ Period, Color             │ (Mutex +    │ Blink: toggle on a timer     │
 │ → update settings,        │  Condvar)   │ wakes up when settings       │
 │   wake the worker         │             │ change, and starts over      │
 └───────────────────────────┘             └──────────────────────────────┘
```

* The C++ version does everything in **one** thread with an event loop
  (sd-event). The Rust version uses **threads**: zbus answers D-Bus calls on
  its own internal thread, and each LED has a small worker thread.
* They share the LED's settings through a **`Mutex`** (a lock, so only one
  thread touches the settings at a time) and a **`Condvar`** ("condition
  variable": a way for one thread to sleep until another wakes it).
* `Arc` ("atomically reference-counted") lets both threads own the same
  shared data. It's freed when the last one lets go.

### 6b. The D-Bus interface

```rust
#[interface(name = "xyz.openbmc_project.Led.Physical")]
impl LedObject {
    #[zbus(property)]
    fn state(&self) -> String { … }                       // read  "State"

    #[zbus(property)]
    fn set_state(&mut self, value: String) -> fdo::Result<()> { … }   // write "State"

    #[zbus(property)]
    fn duty_on(&self) -> u8 { … }                         // "DutyOn", D-Bus type y
    #[zbus(property)]
    fn set_duty_on(&mut self, value: u8) { … }

    #[zbus(property)]
    fn period(&self) -> u16 { … }                         // "Period", D-Bus type q
    #[zbus(property)]
    fn set_period(&mut self, value: u16) { … }

    #[zbus(property(emits_changed_signal = "const"))]
    fn color(&self) -> String { … }                       // "Color", read-only, never changes
}
```

* `#[interface(…)]` and `#[zbus(property)]` are **attributes**: instructions
  to a zbus code generator that runs while compiling. From these few lines,
  zbus generates everything the C++ version writes by hand: the vtable,
  reading and writing the D-Bus messages, and the `PropertiesChanged` signals.
* **Names:** zbus turns `duty_on` into the D-Bus property name `DutyOn`, and
  `set_duty_on` is recognised as its setter.
* **Types:** taken from the Rust types: `String` → `s`, `u8` → `y`,
  `u16` → `q`. Those match the
  [`Led.Physical` definition](hook-up-identify-and-heartbeat-leds_cpp.md#2-how-the-pieces-fit-together).
* **Errors:** `set_state` returns `fdo::Result<()>`. An unknown value returns
  `fdo::Error::InvalidArgs(…)`, the standard D-Bus "invalid arguments"
  error, which the caller sees as `Unknown State value: …`.

### 6c. Publishing objects and claiming the name

```rust
let mut builder = connection::Builder::system()?;           // connect to the system D-Bus
for (dbus_name, gpio_line) in LEDS {
    // … request the GPIO line, start the worker thread …
    builder = builder.serve_at(format!("{PATH_PREFIX}{dbus_name}"), LedObject { shared })?;
}
let _connection = builder.name(BUS_NAME)?.build()?;         // claim the name, start serving
```

* `serve_at(path, object)` adds an object to publish.
* `build()` connects and starts serving. zbus's builder registers all the
  objects **before** it requests the name. I checked this in zbus 5.19's
  source (`connection/builder.rs`). The object mapper therefore sees all four
  LEDs the moment the name appears. The C++ version has to get this order
  right itself.

### 6d. The LED worker

`run_led()` turns the current settings into a list of **steps**: a level and
how long to hold it.

| State | Steps |
| --- | --- |
| Off | `(off, until changed)` |
| On | `(on, until changed)` |
| Blink | `(on, Period × DutyOn ÷ 100 ms)`, `(off, the rest of the period)`, repeated |

* For each step, the worker sets the line, then **sleeps on the Condvar**
  (`wait_while` or `wait_timeout_while`). It wakes when the time is up, or
  as soon as a D-Bus write changes the settings.
* Every change increases a `generation` counter. The worker compares it with
  the one it started from, to know it must start over with the new settings.
* `DutyOn` and `Period` changes only restart the worker while blinking; in
  any other state they're just stored.

**Glitch-free:** each line is requested once, as an output starting at 0
(`as_output(Value::Inactive)`), and kept by its worker thread for as long as
the program runs.

### 6e. Stopping

There's no special stop handling. On `systemctl stop` (signal `SIGTERM`) or
Ctrl-C, the program ends at once. The kernel closes its GPIO line handles,
which releases the lines, and on this chip they become inputs, so the LEDs go
dark. That's the same end result as the C++ version, without its
`stopping` message.

---

## 7. Troubleshooting

The [C++ guide's troubleshooting](hook-up-identify-and-heartbeat-leds_cpp.md#9-troubleshooting)
applies to the board side, with `bbb-led-standin-rs` in place of
`bbb-led-standin`. Rust-specific items:

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error: Failed to connect to address 'unix:path=/var/run/dbus/system_bus_socket'` | Not running on the board (no system D-Bus) | Run it on the board |
| `error: … NameTaken` or `File exists`-style error claiming the name | The C++ version (or another copy) is running | Remove the C++ version first (its section 11), or stop the other copy |
| (PC) `the lock file … needs to be updated but --locked was passed` | `Cargo.lock` missing or edited | Download it again |
| (PC) `linking with 'cc' failed` | `.cargo/config.toml` missing | Download it again (folder `.cargo`, with a dot) |
| (PC) `can't find crate for 'std'` | ARM target not installed | `rustup target add armv7-unknown-linux-gnueabihf` |

---

## 8. Remove everything

This undoes section 4, so the board is back to how it was before (for
example, to go back to the C++ version). Run on the board:

```sh
systemctl disable --now bbb-led-standin-rs.service
rm /usr/local/bin/bbb-led-standin-rs
rm /etc/systemd/system/bbb-led-standin-rs.service
systemctl daemon-reload
rm /etc/phosphor-led-manager/led-group-config.json
rmdir /etc/phosphor-led-manager
systemctl restart xyz.openbmc_project.LED.GroupManager.service
rm ~/bbb-led-standin-rs ~/led-group-config.json ~/bbb-led-standin-rs.service   # optional
```

| Command | What it does |
| --- | --- |
| `systemctl disable --now …` | Stop it and remove it from the boot sequence. The LED lines are released, so the LEDs go dark. |
| `rm …` + `systemctl daemon-reload` | Delete the program and the unit file, and make systemd forget the unit |
| `rm …json`, `rmdir …` | Delete the LED configuration and its (now empty) folder |
| `systemctl restart …GroupManager…` | The LED manager restarts with no configuration and goes back to waiting, as before |
| last line | Delete the copies in the home folder |

Check, as in the
[C++ guide's section 11, step 5](hook-up-identify-and-heartbeat-leds_cpp.md#11-remove-everything-before-trying-the-rust-version):

```sh
systemctl status bbb-led-standin-rs.service      # "could not be found"
gpioinfo | grep led                              # all four "unused input"
ls /usr/local/bin /etc/phosphor-led-manager      # empty / "No such file or directory"
```
