# Hook up the identify and heartbeat LEDs (C++ stand-in)

This guide makes the web UI's **"System identify LED"** switch (and the
matching Redfish request) blink a real LED on the BeagleBone, and makes a
second LED show that the BMC has finished booting. It does it **live**: no
image rebuild, just files added to the running board.

| LED | Shows | Driven by the OpenBMC LED group |
| --- | --- | --- |
| **USR3** | **Identify**: blinks once a second while identify is on | `enclosure_identify_blink` (and `enclosure_identify`) |
| **USR0** | **BMC booted**: a short flash once a second once OpenBMC is up | `bmc_booted` |

There's a [Rust version](hook-up-identify-and-heartbeat-leds_rust.md) of this
guide, with an identical result. [Section 11](#11-remove-everything-before-trying-the-rust-version)
removes everything this guide adds, so you can try the Rust version next.

> **What was tested, and how.**
> * **The build:** the program was cross-compiled on **Ubuntu 24.04** with the
>   commands in section 4. It was linked against the `libsystemd` copied from
>   our released image.
> * **Against the board's libraries:** it was run in an ARM emulator against
>   the libraries copied from our image (glibc 2.43, libstdc++, libsystemd).
>   It starts, and reports a clear error when there's no GPIO or D-Bus.
> * **The D-Bus side:** a PC build of the same source was run with
>   `--dry-run` on a private test D-Bus. `busctl` showed the four LED objects
>   with the standard properties and types. Setting `DutyOn`, `Period` and
>   `State` exactly the way OpenBMC's LED manager does produced the right
>   on/off pattern and timing, an invalid value was rejected, and `SIGTERM`
>   stopped it cleanly.
> * **End to end on the PC:** see [section 6e](#6e-what-was-tested-end-to-end-on-a-pc).
> * **Not yet:** running on the real board. Sections 5 and 6 are written so
>   that each step tells you what you should see.

---

## Contents

1. [Why a stand-in is needed](#1-why-a-stand-in-is-needed)
2. [How the pieces fit together](#2-how-the-pieces-fit-together)
3. [The files](#3-the-files)
4. [Build on Ubuntu](#4-build-on-ubuntu)
5. [Install on the board](#5-install-on-the-board)
6. [Check every layer](#6-check-every-layer)
7. [How the C++ program works](#7-how-the-c-program-works)
8. [The LED configuration and the service file, explained](#8-the-led-configuration-and-the-service-file-explained)
9. [Troubleshooting](#9-troubleshooting)
10. [After the image rebuild](#10-after-the-image-rebuild)
11. [Remove everything (before trying the Rust version)](#11-remove-everything-before-trying-the-rust-version)

---

## 1. Why a stand-in is needed

OpenBMC drives LEDs in layers. On a normal OpenBMC machine:

```
Web UI switch / Redfish PATCH LocationIndicatorActive
        │
        ▼
bmcweb ──► D-Bus: set "Asserted" on /xyz/openbmc_project/led/groups/enclosure_identify_blink
        │
        ▼
phosphor-ledmanager (service xyz.openbmc_project.LED.GroupManager)
        │  reads led-group-config.json: which physical LEDs belong to each group
        ▼
D-Bus: set "State" on /xyz/openbmc_project/led/physical/<name>   (interface xyz.openbmc_project.Led.Physical)
        │
        ▼
phosphor-led-sysfs (service xyz.openbmc_project.LED.Controller)
        │  writes /sys/class/leds/<name>/brightness or trigger
        ▼
Linux kernel LED driver ──► GPIO pin ──► LED
```

On our image:
* **Everything down to phosphor-ledmanager is present.** It only lacks its
  configuration file, so today it waits forever for one (see
  [Troubleshooting](#9-troubleshooting)).
* **The bottom two layers don't work.** Our kernel was built without the LED
  driver (`CONFIG_LEDS_CLASS` is not set), so there's no `/sys/class/leds`,
  and phosphor-led-sysfs has no LEDs to publish.

The **stand-in** replaces those bottom two layers with one small program. It
publishes the same standard `xyz.openbmc_project.Led.Physical` D-Bus objects
that phosphor-led-sysfs would, and drives the GPIO pins directly with
libgpiod. Everything above it stays standard OpenBMC, unchanged.

**It uses the same object names phosphor-led-sysfs will use** after the image
is rebuilt with the kernel LED driver. phosphor-led-sysfs turns the kernel's
LED label `device:color:function` into `device_function_color`. So
`beaglebone:green:usr3` becomes `beaglebone_usr3_green`. That means the LED
configuration file you write here is **already the final one**: after the
rebuild you delete the stand-in, and nothing else changes
([section 10](#10-after-the-image-rebuild)).

---

## 2. How the pieces fit together

```
                         ┌─────────────────────────────────────────────┐
 Web UI / Redfish ──────►│ bmcweb                                      │  (standard)
                         └───────────────┬─────────────────────────────┘
                                         │ Asserted = true
                         ┌───────────────▼─────────────────────────────┐
 /etc/phosphor-led-      │ phosphor-ledmanager                         │  (standard;
 manager/led-group- ────►│   groups: enclosure_identify_blink,         │   we add its
 config.json  (NEW)      │           enclosure_identify, bmc_booted    │   config file)
                         └───────────────┬─────────────────────────────┘
                                         │ asks the object mapper: "who serves
                                         │ /xyz/openbmc_project/led/physical/beaglebone_usr3_green?"
                         ┌───────────────▼─────────────────────────────┐
                         │ xyz.openbmc_project.ObjectMapper            │  (standard)
                         └───────────────┬─────────────────────────────┘
                                         │ "xyz.openbmc_project.LED.GpioStandIn"
                         ┌───────────────▼─────────────────────────────┐
 /usr/local/bin/         │ bbb-led-standin   (NEW, this guide)         │
 bbb-led-standin    ────►│   D-Bus objects (xyz.openbmc_project.       │
 /etc/systemd/system/    │     Led.Physical): State, DutyOn, Period    │
 bbb-led-standin.service │   holds GPIO lines [usr0 led]..[usr3 led]   │
                         └───────────────┬─────────────────────────────┘
                                         ▼
                              USR0 … USR3 LEDs on the board
```

* **The object mapper** (`xyz.openbmc_project.ObjectMapper`) is OpenBMC's
  directory of who serves which D-Bus objects. Whenever a program takes a
  D-Bus name, the mapper looks at ("introspects") all its objects and records
  them. phosphor-ledmanager asks the mapper which program serves an LED
  object, then sets the LED's properties on that program.
* **The stand-in's bus name** is `xyz.openbmc_project.LED.GpioStandIn`. It
  can't use phosphor-led-sysfs's name, `xyz.openbmc_project.LED.Controller`,
  because that program is still running (with no LEDs). Thanks to the mapper,
  the name doesn't matter to phosphor-ledmanager.
* **The stand-in publishes all four user LEDs.** USR1 and USR2 aren't used by
  any group yet, but they're there if you want to add groups later.

| D-Bus object (under `/xyz/openbmc_project/led/physical/`) | LED | GPIO line name |
| --- | --- | --- |
| `beaglebone_heartbeat_green` | USR0 | `[usr0 led]` |
| `beaglebone_mmc0_green` | USR1 | `[usr1 led]` |
| `beaglebone_usr2_green` | USR2 | `[usr2 led]` |
| `beaglebone_usr3_green` | USR3 | `[usr3 led]` |

**The `xyz.openbmc_project.Led.Physical` interface** (defined in OpenBMC's
`phosphor-dbus-interfaces`, `yaml/xyz/openbmc_project/Led/Physical.interface.yaml`):

| Property | D-Bus type | Values |
| --- | --- | --- |
| `State` | `s` (text) | `xyz.openbmc_project.Led.Physical.Action.Off`, `.On` or `.Blink` |
| `DutyOn` | `y` (byte) | Percent of each blink period the LED is on (default 50) |
| `Period` | `q` (16-bit unsigned) | Blink period in milliseconds (default 1000) |
| `Color` | `s`, read-only | `xyz.openbmc_project.Led.Physical.Palette.Green` |

For a blink, phosphor-ledmanager sets `DutyOn`, then `Period`, then `State`.

---

## 3. The files

All in [`led-standin_cpp/`](led-standin_cpp/):

| File | What it is | Where it goes on the board |
| --- | --- | --- |
| [`bbb-led-standin.cpp`](led-standin_cpp/bbb-led-standin.cpp) | The stand-in program's source | Compiled on the PC; the program goes to `/usr/local/bin/bbb-led-standin` |
| [`led-group-config.json`](led-standin_cpp/led-group-config.json) | Which LEDs belong to which LED group | `/etc/phosphor-led-manager/led-group-config.json` |
| [`bbb-led-standin.service`](led-standin_cpp/bbb-led-standin.service) | systemd unit that starts the stand-in at boot | `/etc/systemd/system/bbb-led-standin.service` |

**Why these locations?**
* `/etc` and `/usr/local` are where an administrator's own additions go.
* phosphor-ledmanager checks `/etc/phosphor-led-manager/` **before** the
  image's own `/usr/share/phosphor-led-manager/` (which is empty in our image).
* systemd checks `/etc/systemd/system/` before the image's
  `/usr/lib/systemd/system/`.
* All of them survive a reboot, but are **wiped by re-flashing** the eMMC.

---

## 4. Build on Ubuntu

The program needs three things to build:

1. the **C++ cross-compiler**;
2. **libgpiod 1.6.5 with its C++ part**, built for ARM;
3. **sd-bus**, the D-Bus library inside **libsystemd**: its header files, and
   a copy of the board's own `libsystemd.so.0` to link against.

Steps 1 and 2 are the same as in the
[C++ cross-compile guide](cross-compile-a-gpio-program_cpp.md). They're
repeated here so this guide stands on its own.

### 4a. Install the tools

```sh
sudo apt update
sudo apt install g++-arm-linux-gnueabihf gcc-arm-linux-gnueabihf build-essential \
                 wget xz-utils file libsystemd-dev
```

| Package | Why |
| --- | --- |
| `g++-arm-linux-gnueabihf`, `gcc-arm-linux-gnueabihf` | The ARM C++ and C cross-compilers |
| `build-essential` | `make`, for building libgpiod |
| `wget`, `xz-utils` | Download and unpack libgpiod's source |
| `file` | Check the result is an ARM program |
| **`libsystemd-dev`** | **The sd-bus and sd-event header files** (`<systemd/sd-bus.h>`, `<systemd/sd-event.h>`). We only use its headers. They're plain C and don't depend on the processor, so the PC's copy works for ARM too. The library itself comes from the board (4d). |

### 4b. Make a working folder and get the source

```sh
mkdir -p ~/bbb-led-cpp && cd ~/bbb-led-cpp
BASE=https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/led-standin_cpp
wget $BASE/bbb-led-standin.cpp $BASE/led-group-config.json $BASE/bbb-led-standin.service
```

`wget` with several addresses downloads each one into the current folder.
**All the commands below are run in `~/bbb-led-cpp`.**

### 4c. Build libgpiod 1.6.5 (with its C++ part) for ARM

Skip this if you already did it in the C++ cross-compile guide and want to
reuse that `sysroot`: copy it with `cp -r ~/bbb-gpio-cpp/sysroot .`.

```sh
wget https://mirrors.edge.kernel.org/pub/software/libs/libgpiod/libgpiod-1.6.5.tar.xz
sha256sum libgpiod-1.6.5.tar.xz
#   must print ae280f697bf035a1fb780c9972e5c81d0d2712b7ab6124fb3fba24619daa72bc
tar xf libgpiod-1.6.5.tar.xz
cd libgpiod-1.6.5
./configure --host=arm-linux-gnueabihf --prefix=$HOME/bbb-led-cpp/sysroot \
            --enable-static --disable-shared --enable-bindings-cxx
make -j$(nproc) && make install
cd ..
```

The options are explained in the
[C++ cross-compile guide, section 5c](cross-compile-a-gpio-program_cpp.md#5c-build-and-install-it-with-the-c-part).
In short:
* build for ARM (`--host`);
* into the private folder `sysroot` (`--prefix`);
* as static libraries built into the program (`--enable-static
  --disable-shared`);
* including the C++ part (`--enable-bindings-cxx`).

### 4d. Add sd-bus: headers from Ubuntu, library from the board

```sh
cp -r /usr/include/systemd sysroot/include/
scp root@evb-beaglebone.local:/usr/lib/libsystemd.so.0 sysroot/lib/
```

| Command | Meaning |
| --- | --- |
| `cp -r /usr/include/systemd sysroot/include/` | Copy **only** the systemd header folder into our private `sysroot`. Never point the cross-compiler at the whole `/usr/include`: that folder holds the PC's own headers, and mixing them into an ARM build causes confusing errors. |
| `scp root@evb-beaglebone.local:/usr/lib/libsystemd.so.0 sysroot/lib/` | Copy the **board's** libsystemd. On the board it's a shortcut (symlink) to `libsystemd.so.0.42.0`; `scp` copies the real file it points to. The linker uses it to check that every sd-bus function we call exists, and records "needs `libsystemd.so.0`" in our program. At run time the board's own copy is used. |

**Why link against the board's copy, not Ubuntu's?**
* Ubuntu's libsystemd is for the PC's processor (x86-64), so the ARM linker
  can't use it.
* The board's copy (systemd 259) is the exact library the program will use.
* Ubuntu 24.04's headers are from an older systemd (255), but sd-bus keeps
  old functions working in new versions, so headers from 255 with the library
  from 259 work. Every function this program uses has existed since systemd
  247 or earlier. Section 6 shows how to check.

### 4e. Compile

```sh
arm-linux-gnueabihf-g++ -std=c++17 -Wall -Wextra -O2 -I sysroot/include \
    -o bbb-led-standin bbb-led-standin.cpp \
    -L sysroot/lib -l:libgpiodcxx.a -l:libgpiod.a -l:libsystemd.so.0
arm-linux-gnueabihf-strip bbb-led-standin
```

| Part | Meaning |
| --- | --- |
| `-std=c++17` | C++ language version |
| `-Wall -Wextra` | Warnings. There should be none. |
| `-I sysroot/include` | Find `gpiod.hpp` and `systemd/sd-bus.h` here |
| `-o bbb-led-standin bbb-led-standin.cpp` | Output name and source file |
| `-L sysroot/lib` | Find the libraries here |
| `-l:libgpiodcxx.a -l:libgpiod.a` | libgpiod's C++ part, then its C part: both **built into** the program. The order matters: the C++ part uses the C part. |
| `-l:libsystemd.so.0` | **Use** the board's libsystemd at run time (not built in) |
| `arm-linux-gnueabihf-strip` | Remove debugging information. The program goes from about 1.2 MB to about 63 KB. |

Check it:

```sh
file bbb-led-standin
arm-linux-gnueabihf-readelf -d bbb-led-standin | grep NEEDED
```

* `file` must say `ARM, EABI5`, `interpreter /lib/ld-linux-armhf.so.3`.
* `NEEDED` must list `libsystemd.so.0`, `libstdc++.so.6`, `libgcc_s.so.1`,
  `libc.so.6` and `ld-linux-armhf.so.3`. All are in our image.

### 4f. Copy the three files to the board

```sh
scp bbb-led-standin led-group-config.json bbb-led-standin.service root@evb-beaglebone.local:
```

They land in `/home/root` on the board. Section 5 puts them in place.

---

## 5. Install on the board

Run these **on the board** (serial console or SSH), one block at a time.

### 5a. First, a dry run in the foreground (optional, recommended)

Before installing anything, run the program by hand **without touching GPIO**:

```sh
cd ~
chmod +x bbb-led-standin
./bbb-led-standin --dry-run
```

* `chmod +x` marks the file as executable (`scp` normally keeps that, but
  this makes sure).
* `--dry-run` publishes the four LED objects on the real system D-Bus, but
  only prints what each LED would do.
* Expected: `bbb-led-standin: serving 4 LEDs as
  xyz.openbmc_project.LED.GpioStandIn (dry run: no GPIO)`, and then it waits.

In a **second** SSH session, poke it the way phosphor-ledmanager will:

```sh
busctl tree xyz.openbmc_project.LED.GpioStandIn
busctl introspect xyz.openbmc_project.LED.GpioStandIn \
    /xyz/openbmc_project/led/physical/beaglebone_usr3_green xyz.openbmc_project.Led.Physical
busctl set-property xyz.openbmc_project.LED.GpioStandIn \
    /xyz/openbmc_project/led/physical/beaglebone_usr3_green \
    xyz.openbmc_project.Led.Physical State s xyz.openbmc_project.Led.Physical.Action.Blink
```

| Command | What it does | Expected |
| --- | --- | --- |
| `busctl tree <service>` | Lists all objects a D-Bus service publishes | The four `…/led/physical/beaglebone_*` objects |
| `busctl introspect <service> <object> <interface>` | Lists an object's properties with their types and values | `.Color s`, `.DutyOn y 50`, `.Period q 1000`, `.State s "…Action.Off"` |
| `busctl set-property <service> <object> <interface> <property> <type> <value>` | Sets one property. `s` is the D-Bus type (text), followed by the value. | The first session prints `beaglebone_usr3_green: Blink (period 1000 ms, on 50 %)`, then `[dry-run] beaglebone_usr3_green = 1` / `= 0` every half second |

Set it back to `…Action.Off`, then stop the dry run with **Ctrl-C** in the
first session. It prints `bbb-led-standin: stopping`.

### 5b. Install the program, the configuration and the service

```sh
mkdir -p /usr/local/bin
install -m 0755 ~/bbb-led-standin /usr/local/bin/bbb-led-standin
mkdir -p /etc/phosphor-led-manager
install -m 0644 ~/led-group-config.json /etc/phosphor-led-manager/led-group-config.json
install -m 0644 ~/bbb-led-standin.service /etc/systemd/system/bbb-led-standin.service
```

| Command | Meaning |
| --- | --- |
| `mkdir -p /usr/local/bin` | Create the folder (our image doesn't have it yet). `-p`: no error if it exists. |
| `install -m 0755 <from> <to>` | Copy a file and set its permissions in one step. `0755` = owner can read, write and run; everyone else can read and run (a program). `0644` = owner read and write, others read (a data file). |
| `/etc/phosphor-led-manager/led-group-config.json` | The exact name and place phosphor-ledmanager looks for first |
| `/etc/systemd/system/bbb-led-standin.service` | systemd's folder for locally added services |

### 5c. Start the stand-in, and make it start at every boot

```sh
systemctl daemon-reload
systemctl enable --now bbb-led-standin.service
systemctl status bbb-led-standin.service
```

| Command | Meaning |
| --- | --- |
| `systemctl daemon-reload` | Make systemd re-read its unit files, so it sees the new one |
| `systemctl enable --now <unit>` | `enable`: start it at every boot (creates a link in `multi-user.target.wants`). `--now`: also start it right now. |
| `systemctl status <unit>` | Shows whether it's running, plus its last log lines |

Expected: `Active: active (running)`, and in the log lines
`bbb-led-standin: serving 4 LEDs as xyz.openbmc_project.LED.GpioStandIn`.
Press **q** to leave `status` if it shows a pager.

Starting can take a few seconds. The service only counts as started once the
object mapper has recorded our LED objects (the `ExecStartPost=mapper wait …`
line, [section 8b](#8b-the-service-file)).

### 5d. Restart the LED manager so it reads its new configuration

```sh
systemctl restart xyz.openbmc_project.LED.GroupManager.service
systemctl status xyz.openbmc_project.LED.GroupManager.service
```

phosphor-ledmanager only reads its configuration when it starts. Until now
it had none and was stuck waiting. Expected: `Active: active (running)`.

### 5e. Turn on the "BMC booted" LED now

```sh
systemctl restart obmc-led-group-start@bmc_booted.service
```

* At every boot, OpenBMC's `obmc-led-group-start@bmc_booted.service` asserts
  the `bmc_booted` group, once the system is up.
* It already ran at this boot, when there was nothing to light. Restarting it
  asserts the group again now.
* Expected: **USR0 starts a short flash once a second**. From the next boot
  on, this happens by itself.

---

## 6. Check every layer

Work from the bottom up. Each step tells you what to expect.

### 6a. The stand-in and its GPIO lines

```sh
gpioinfo | grep led
```

All four lines show `"bbb-led-standin" output … [used]`: the stand-in holds
them. USR3 is low (off) until identify is turned on.

```sh
journalctl -u bbb-led-standin.service -b --no-pager | tail
```

* `journalctl` shows a service's log; `-u` picks the unit; `-b` limits it to
  this boot; `--no-pager` prints straight to the terminal.
* You'll see one line per change, e.g. `beaglebone_heartbeat_green: Blink
  (period 1000 ms, on 10 %)`.

### 6b. The object mapper knows the LEDs

```sh
mapper get-service /xyz/openbmc_project/led/physical/beaglebone_usr3_green
```

Expected: `xyz.openbmc_project.LED.GpioStandIn`. This is exactly the question
phosphor-ledmanager asks the mapper.

### 6c. The LED groups

```sh
busctl tree xyz.openbmc_project.LED.GroupManager
busctl get-property xyz.openbmc_project.LED.GroupManager \
    /xyz/openbmc_project/led/groups/enclosure_identify_blink xyz.openbmc_project.Led.Group Asserted
```

* `tree`: the three groups from our configuration,
  `/xyz/openbmc_project/led/groups/bmc_booted`, `…/enclosure_identify` and
  `…/enclosure_identify_blink`.
* `get-property … Asserted`: `b false` (`b` = true/false type), until
  identify is turned on.

Turn identify on and off directly at the group level:

```sh
busctl set-property xyz.openbmc_project.LED.GroupManager \
    /xyz/openbmc_project/led/groups/enclosure_identify_blink xyz.openbmc_project.Led.Group Asserted b true
#   USR3 blinks once a second
busctl set-property xyz.openbmc_project.LED.GroupManager \
    /xyz/openbmc_project/led/groups/enclosure_identify_blink xyz.openbmc_project.Led.Group Asserted b false
#   USR3 off
```

### 6d. From the web UI and Redfish

* **Web UI:** Overview → **Inventory and LEDs** card → **System identify LED**
  switch. On: USR3 blinks. Off: USR3 goes dark.
* **Redfish from the PC**, the same request the web UI sends:

  ```sh
  curl -k -u root -X PATCH -H "Content-Type: application/json" \
       -d '{"LocationIndicatorActive": true}' \
       https://evb-beaglebone.local/redfish/v1/Systems/system
  curl -k -u root https://evb-beaglebone.local/redfish/v1/Systems/system | grep LocationIndicatorActive
  ```

  | Part | Meaning |
  | --- | --- |
  | `-k` | Accept the BMC's self-made HTTPS certificate |
  | `-u root` | Log in as `root`. curl asks for the password. |
  | `-X PATCH` | Change part of a resource (Redfish's "update" method) |
  | `-H "Content-Type: application/json"` | The body is JSON |
  | `-d '{"LocationIndicatorActive": true}'` | The change: identify on (`false` = off) |
  | `…/redfish/v1/Systems/system` | The resource for the system (the "host") |

  The second command reads the system back. It should show
  `"LocationIndicatorActive": true`.
* **What happens inside:** bmcweb sets `Asserted` on the
  `enclosure_identify_blink` group. Only if that group doesn't exist does it
  fall back to `enclosure_identify` (bmcweb `redfish-core/lib/led.hpp`). Our
  configuration has both, so the blink group is the one used.

**Reboot test:** `reboot`. After the board is back:
* USR0 flashes by itself;
* identify is off;
* the web UI switch works again.

### 6e. What was tested end to end on a PC

Before writing this guide, the whole chain above the GPIO pins was run on a
PC, on a private test D-Bus, with **OpenBMC's real programs** built from
source at the **same versions as in our image**:
* `phosphor-ledmanager` at `bc69dd96`;
* the object mapper (`mapperx`) and its `mapper` tool from `phosphor-objmgr`
  at `c0ad7b4f`;
* their helper libraries at their current versions.

The stand-in ran with `--dry-run`. Both the C++ and the Rust stand-in were
tested.

| Step (as on the board) | Result |
| --- | --- |
| Start the mapper, then the stand-in; run `mapper wait …/beaglebone_usr3_green` (the service's `ExecStartPost`) | Returned at once, with success |
| `mapper get-service …/beaglebone_usr3_green` | `xyz.openbmc_project.LED.GpioStandIn` |
| Start `phosphor-ledmanager` with **this guide's `led-group-config.json`** | Accepted. `busctl tree` showed the three groups. (With the `Priority` lines removed, it refused to start: `ConfigValidationException`.) |
| `busctl set-property … groups/bmc_booted … Asserted b true` (the exact command `obmc-led-group-start@bmc_booted.service` runs) | Stand-in: `beaglebone_heartbeat_green: Blink (period 1000 ms, on 10 %)` and the flashes |
| `… groups/enclosure_identify_blink … Asserted b true` (what bmcweb sets for identify on) | Stand-in: `beaglebone_usr3_green: Blink (period 1000 ms, on 50 %)`, toggling every 0.5 s |
| Also assert `enclosure_identify` | No change: Blink kept, because of `Priority: Blink` |
| Release `enclosure_identify_blink` | USR3 changed to On (only `enclosure_identify` left) |
| Release `enclosure_identify` | USR3 Off |
| LED manager log | No errors |

Not covered by this test:
* **bmcweb** itself: its D-Bus call was reproduced with `busctl`, which sends
  the same request;
* **the real GPIO pins**;
* **systemd's start-up ordering at boot.**

Those are what sections 5 and 6 check on the board.

---

## 7. How the C++ program works

The source is [`bbb-led-standin.cpp`](led-standin_cpp/bbb-led-standin.cpp),
about 350 lines, commented throughout. Its parts:

### 7a. Libraries

| Library | Header | Used for |
| --- | --- | --- |
| **sd-bus** (in libsystemd) | `<systemd/sd-bus.h>` | Connecting to the system D-Bus, publishing objects and their properties, claiming a bus name |
| **sd-event** (in libsystemd) | `<systemd/sd-event.h>` | The **event loop**: one loop that waits for D-Bus messages, blink timers and stop signals, and calls our code for each |
| **libgpiod 1.6 C++** | `<gpiod.hpp>` | Finding the LED lines by name, holding them as outputs, setting their values |

**sd-bus is a C library.** OpenBMC's own C++ programs use **sdbusplus**, a C++
wrapper around sd-bus. sdbusplus generates code from the interface YAML
files, so it's normally only built inside the Yocto build. Using sd-bus
directly shows exactly what sdbusplus does for you, and builds anywhere.

### 7b. The D-Bus interface description (vtable)

```cpp
const sd_bus_vtable ledVtable[] = {
    SD_BUS_VTABLE_START(0),
    SD_BUS_WRITABLE_PROPERTY("State",  "s", getProperty, setProperty, 0,
                             SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE),
    SD_BUS_WRITABLE_PROPERTY("DutyOn", "y", getProperty, setProperty, 0,
                             SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE),
    SD_BUS_WRITABLE_PROPERTY("Period", "q", getProperty, setProperty, 0,
                             SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE),
    SD_BUS_PROPERTY("Color", "s", getProperty, 0, SD_BUS_VTABLE_PROPERTY_CONST),
    SD_BUS_VTABLE_END,
};
```

* A **vtable** ("virtual table") is sd-bus's description of an interface: a
  list of properties (and methods and signals, which we don't have).
* Each entry gives:
  * the property **name**;
  * its D-Bus **type**: `s` text, `y` byte, `q` 16-bit unsigned;
  * the **functions** that read it (`getProperty`) and write it
    (`setProperty`);
  * **flags**.
* Flags: `EMITS_CHANGE` advertises that a `PropertiesChanged` signal is sent
  when the value changes. `CONST` means it never changes (Color).
* `sd_bus_add_object_vtable(bus, nullptr, path, interface, ledVtable, led)`
  publishes the vtable at one object path. The last argument, `led`, is
  passed back to the read and write functions as `userdata`, so they know
  which LED they're dealing with. The same vtable serves all four objects.

### 7c. Reading and writing properties

```cpp
int setProperty(sd_bus* bus, const char* path, const char* interface, const char* property,
                sd_bus_message* value, void* userdata, sd_bus_error* error)
{
    auto* led = static_cast<Led*>(userdata);           // which LED
    if (std::strcmp(property, "State") == 0) {
        const char* text = nullptr;
        sd_bus_message_read(value, "s", &text);        // read the new value (type s)
        auto action = parseAction(text);               // "…Action.Blink" -> Action::Blink
        if (!action)
            return sd_bus_error_setf(error, SD_BUS_ERROR_INVALID_ARGS,
                                     "Unknown State value: %s", text);
        led->setState(*action);
    } else if ... DutyOn ("y") ... Period ("q") ...
    sd_bus_emit_properties_changed(bus, path, interface, property, nullptr);
    return 1;
}
```

* sd-bus calls `setProperty` when any program does a D-Bus `Properties.Set`
  on one of our objects. phosphor-ledmanager and `busctl set-property` both
  do this.
* `sd_bus_message_read(value, "s", &text)` takes the value out of the
  message, checking it has the type we expect.
* A bad value is answered with a standard D-Bus error (`InvalidArgs`), which
  the caller sees as `Unknown State value: …`.
* `sd_bus_emit_properties_changed` tells anyone watching that the property
  changed.
* `getProperty` works the other way round: `sd_bus_message_append(reply, "s",
  …)` puts the current value into the reply.

### 7d. Driving the LED, and blinking

The `Led` class holds one GPIO line and the LED's three settings. `apply()`
puts the hardware into the current state:

| State | What happens |
| --- | --- |
| Off | Line set to 0 |
| On | Line set to 1 |
| Blink | Line set to 1, and a **timer** started for the "on" time: `Period × DutyOn ÷ 100` ms. When it fires, the line toggles and the timer restarts for the "off" time, and so on. |

* The timer is an **sd-event one-shot timer**
  (`sd_event_add_time_relative(event, &timer, CLOCK_MONOTONIC, microseconds,
  …, &Led::onTimer, this)`).
* `CLOCK_MONOTONIC` is a clock that never jumps, even if someone changes the
  date. Every state change stops the old timer first.
* **Glitch-free:** each line is requested once, at start-up, as an output
  starting at 0 (`line.request({…, DIRECTION_OUTPUT, 0}, 0)`), and only its
  value changes after that. When the program ends, libgpiod releases the
  lines, and on this chip they become inputs, so the LEDs go dark.

### 7e. Start-up order matters

```cpp
for (auto& led : leds)
    sd_bus_add_object_vtable(bus, nullptr, led->path().c_str(), ledInterface, ledVtable, led.get());
sd_bus_request_name(bus, busName, 0);
```

* The objects are published **before** the bus name is claimed.
* The object mapper examines a program's objects at the moment its name
  appears. Claiming the name first could let the mapper look too early and
  record nothing.

### 7f. The event loop and stopping

* `sd_bus_attach_event` lets the event loop handle D-Bus messages.
* `sd_event_add_signal` adds `SIGTERM` (sent by `systemctl stop`) and
  `SIGINT` (Ctrl-C). With no handler given, sd-event's default is to **end
  the loop**.
* `sd_event_loop` runs until then. After it returns, the `Led` objects are
  destroyed: the timers stop and the GPIO lines are released.

---

## 8. The LED configuration and the service file, explained

### 8a. The LED configuration

[`led-group-config.json`](led-standin_cpp/led-group-config.json):

```json
{
    "leds": [
        {   "group": "enclosure_identify_blink",
            "members": [ { "Name": "beaglebone_usr3_green", "Action": "Blink",
                           "DutyOn": 50, "Period": 1000, "Priority": "Blink" } ] },
        {   "group": "enclosure_identify",
            "members": [ { "Name": "beaglebone_usr3_green", "Action": "On",
                           "Priority": "Blink" } ] },
        {   "group": "bmc_booted",
            "members": [ { "Name": "beaglebone_heartbeat_green", "Action": "Blink",
                           "DutyOn": 10, "Period": 1000, "Priority": "Blink" } ] }
    ]
}
```

| Group | Who asserts it | LED | What it does |
| --- | --- | --- | --- |
| `enclosure_identify_blink` | bmcweb, when identify is turned on (web UI or Redfish) | USR3 | Blink: 1000 ms period, on 50 % = 0.5 s on, 0.5 s off |
| `enclosure_identify` | bmcweb only uses it if `enclosure_identify_blink` doesn't exist. It's a standard OpenBMC group name that other tools may use, so it's defined for completeness. You can also assert it by hand (section 6c). | USR3 | On |
| `bmc_booted` | `obmc-led-group-start@bmc_booted.service`, at the end of every boot | USR0 | Blink: 1000 ms period, on 10 % = a 0.1 s flash each second |

* **`Name`** is the LED's object name under
  `/xyz/openbmc_project/led/physical/`.
* **`Priority`** is required on every member by this version of
  phosphor-ledmanager.
  * If two asserted groups want the same LED in different states, the
    Priority state wins. Here, if both USR3 groups are asserted at once,
    **Blink** wins over On.
  * An LED must use the same Priority in every group it appears in.
* The full format is described in the
  [phosphor-led-manager README](https://github.com/openbmc/phosphor-led-manager/blob/bc69dd96f622631a749bba1605efce4df51d4a7c/README.md).
  [`web-ui-explained.md`](web-ui-explained.md) has more on the web UI side,
  and [`turn-on-led-guide.md`](turn-on-led-guide.md) on the LED pins.

### 8b. The service file

[`bbb-led-standin.service`](led-standin_cpp/bbb-led-standin.service):

```ini
[Unit]
Description=BeagleBone LED stand-in (GPIO-backed xyz.openbmc_project.Led.Physical)
Wants=xyz.openbmc_project.ObjectMapper.service
After=xyz.openbmc_project.ObjectMapper.service
Before=xyz.openbmc_project.LED.GroupManager.service obmc-led-group-start@bmc_booted.service

[Service]
Type=dbus
BusName=xyz.openbmc_project.LED.GpioStandIn
ExecStart=/usr/local/bin/bbb-led-standin
ExecStartPost=/usr/bin/mapper wait /xyz/openbmc_project/led/physical/beaglebone_usr3_green
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

| Line | Meaning |
| --- | --- |
| `Wants=` / `After=…ObjectMapper.service` | Start the object mapper too, and start after it |
| `Before=…GroupManager… …bmc_booted…` | At boot, be ready before the LED manager and before the "BMC booted" group is asserted |
| `Type=dbus` + `BusName=` | The service counts as **started** only once it has claimed this D-Bus name |
| `ExecStart=` | The program to run |
| `ExecStartPost=/usr/bin/mapper wait <object>` | After starting, wait until the **object mapper** has recorded our USR3 object (`mapper` is OpenBMC's mapper command-line tool). Only then is the service "started", so the units ordered after it never ask the mapper too early. |
| `Restart=on-failure` | If it crashes, start it again |
| `WantedBy=multi-user.target` | `systemctl enable` hooks it into the normal boot |

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `bbb-led-standin: error: GPIO line not found: [usr0 led]` | Line names differ | Compare with `gpioinfo \| grep led` |
| `error: … Device or resource busy` | Another program holds an LED line (e.g. a `gpioset`, or an earlier copy still running) | `gpioinfo \| grep led` shows the owner. Stop it. |
| `error: request bus name: File exists` | Another copy is running (e.g. the dry run, or the Rust version) | Stop it: Ctrl-C, or `systemctl stop bbb-led-standin-rs` |
| `error: connect to system D-Bus …` | Not running on the board, or D-Bus not up | Run it on the board, after boot |
| `systemctl status` shows `activating (start-post)` for a long time | `mapper wait` hasn't seen our objects | `journalctl -u bbb-led-standin -b`, and `systemctl status xyz.openbmc_project.ObjectMapper` |
| GroupManager `activating` for about 90 s, then failing | It found no configuration file and is waiting for entity-manager (not in our image) | Check the file is at exactly `/etc/phosphor-led-manager/led-group-config.json`. Then `systemctl restart xyz.openbmc_project.LED.GroupManager`. |
| GroupManager fails at start | Configuration rejected, e.g. invalid JSON or a missing `Priority` | `journalctl -u xyz.openbmc_project.LED.GroupManager -b` shows the reason |
| Web UI switch does nothing | Groups missing, or GroupManager not running | Check 6c. Then `journalctl -u xyz.openbmc_project.LED.GroupManager -b` for `Error setting property for physical LED`, which means it couldn't reach the stand-in (check 6b). |
| USR0 stays dark after a reboot | `bmc_booted` was asserted before the stand-in was ready | `systemctl restart obmc-led-group-start@bmc_booted.service`, and tell me: the service ordering should prevent this |
| (PC) `fatal error: systemd/sd-bus.h: No such file or directory` | Step 4d skipped | `cp -r /usr/include/systemd sysroot/include/` (needs `libsystemd-dev`) |
| (PC) `cannot find -l:libsystemd.so.0` | Board's library not copied | `scp root@evb-beaglebone.local:/usr/lib/libsystemd.so.0 sysroot/lib/` |
| (board) `version 'LIBSYSTEMD_2xx' not found` | Built against a newer libsystemd than the board's | Make sure you linked against the board's copy (4d) |

---

## 10. After the image rebuild

Once the image is rebuilt with the kernel LED driver (and phosphor-led-sysfs
publishes the LEDs itself):

1. Remove the stand-in, as in [section 11](#11-remove-everything-before-trying-the-rust-version),
   steps 1 and 2, but **keep the LED configuration**.
2. Restart the LED manager. The same object names now come from
   `xyz.openbmc_project.LED.Controller`. Check with `mapper get-service`.
3. Decide who owns USR0:
   * **the kernel's heartbeat** (the classic double pulse, from the moment
     Linux starts): remove the `bmc_booted` group from the configuration;
   * **OpenBMC's "booted" flash**: keep it.
4. Bake the configuration into the image: a recipe that installs it as
   `/usr/share/phosphor-led-manager/led-group-config.json`.

---

## 11. Remove everything (before trying the Rust version)

This undoes sections 5b–5e, so the board is back to how it was before this
guide. Run on the board.

**1. Stop the stand-in and remove it from the boot sequence:**

```sh
systemctl disable --now bbb-led-standin.service
```

`disable` removes the boot-time link that `enable` created; `--now` also
stops it. The GPIO lines are released, so all four LEDs go dark.

**2. Delete the program and the service file, and tell systemd:**

```sh
rm /usr/local/bin/bbb-led-standin
rm /etc/systemd/system/bbb-led-standin.service
systemctl daemon-reload
```

**3. Delete the LED configuration and restart the LED manager:**

```sh
rm /etc/phosphor-led-manager/led-group-config.json
rmdir /etc/phosphor-led-manager
systemctl restart xyz.openbmc_project.LED.GroupManager.service
```

* `rmdir` removes the folder only if it's empty. If it complains, something
  else is in it: look before deleting.
* Without a configuration, the LED manager goes back to waiting, exactly as
  before. The Rust guide installs its own copy of the same configuration.

**4. Optional: delete the copies in the home folder:**

```sh
rm ~/bbb-led-standin ~/led-group-config.json ~/bbb-led-standin.service
```

**5. Check it's all gone:**

```sh
systemctl status bbb-led-standin.service
busctl tree xyz.openbmc_project.LED.GpioStandIn
gpioinfo | grep led
ls /usr/local/bin /etc/phosphor-led-manager
```

| Command | Expected after removal |
| --- | --- |
| `systemctl status bbb-led-standin.service` | `Unit bbb-led-standin.service could not be found.` |
| `busctl tree xyz.openbmc_project.LED.GpioStandIn` | An error: the name has no owner |
| `gpioinfo \| grep led` | All four lines `unused input` |
| `ls /usr/local/bin /etc/phosphor-led-manager` | `/usr/local/bin` empty; `/etc/phosphor-led-manager`: `No such file or directory` |

A reboot isn't needed, but it's a good final check that nothing comes back.
You're now ready for the [Rust version](hook-up-identify-and-heartbeat-leds_rust.md).
