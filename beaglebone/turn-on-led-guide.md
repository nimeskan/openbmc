# Turn on an LED: driving a GPIO pin by hand

This guide turns on the **USR3** LED on the BeagleBone Black from the board's
command line, using only tools that are already in our OpenBMC image. Along the
way it shows how to find out **which GPIO controller and pin** an LED is on,
**which register** decides what a pin is used for (the "pin mux"), and **where
every number comes from**, so you can do the same for any other pin.

Nothing here changes the image or survives a reboot. It's all live
experimenting.

> **What was checked, and how.**
> * **On our board:** the LED pin is on `gpiochip0`, its pin-mux register
>   reads `0x27` (GPIO mode), and `gpioset --mode=wait gpiochip0 24=1` **lit
>   USR3**. Lines 21, 22 and 23 lit USR0, USR1 and USR2 the same way.
> * **Against our image's own files:** the device tree (`am335x-boneblack.dtb`)
>   and the kernel settings.
> * **Against source code:** libgpiod 1.6.5 and the Linux 6.18 GPIO driver.
> * **Board commands that read the device tree** (`xxd`, `tr`, `find`) were run
>   with the image's own BusyBox in an emulator.

**Before you start:** be logged in on the board, over the serial console or
SSH (see the [Ubuntu](connecting-from-an-ubuntu-pc.md) or
[Windows](connecting-from-a-windows-pc.md) connection guide).

---

## Contents

1. [The names you'll meet](#1-the-names-youll-meet)
2. [Step 1: find the pin](#2-step-1-find-the-pin)
3. [Step 2: check the pin mux](#3-step-2-check-the-pin-mux)
4. [Step 3: turn the LED on and off](#4-step-3-turn-the-led-on-and-off)
5. [Where the numbers come from](#5-where-the-numbers-come-from)
6. [What happens underneath](#6-what-happens-underneath)
7. [Troubleshooting](#7-troubleshooting)
8. [Limits, and what comes next](#8-limits-and-what-comes-next)
9. [Quick reference](#9-quick-reference)

---

## 1. The names you'll meet

One physical pin goes by several names, depending on who is talking about it:

| Name | Who uses it | Meaning |
| --- | --- | --- |
| **USR3** | The BeagleBone board | The fourth of the four small LEDs near the Ethernet socket |
| **GPMC_A8** | The processor's datasheet | The processor pin it's wired to (named after its first function) |
| **GPIO1_24** | The processor's GPIO hardware | GPIO bank (controller) **1**, pin **24** |
| **`conf_gpmc_a8`** at **`0x44E10860`** | The processor's Control Module | The register that chooses the pin's function (its **pad mux** register) |
| **`[usr3 led]`** | The device tree (`gpio-line-names`) | A friendly name for the pin |
| **`gpiochip0`, line 24** | Linux | The GPIO controller number Linux gave bank 1 on this boot, and the pin number within it |

**Pin mux, in one sentence.** Each pin of the AM335x processor can do up to
eight different jobs: GPIO, UART, SPI and so on. A small register per pin, its
**pad configuration register**, selects which job it does. Only in **mode 7**
is this pin connected to the GPIO hardware.

**Why our image is different from a stock BeagleBone.** Normally the kernel's
LED driver owns the four USR LEDs. It sets their pin mux and makes them blink:
heartbeat, SD card activity and so on. **Our image's kernel has no LED driver**
(`CONFIG_LEDS_CLASS` is not set; see the explanation in
[section 8](#8-limits-and-what-comes-next)). So the LEDs are unclaimed, and we
can drive them ourselves as plain GPIO pins.

---

## 2. Step 1: find the pin

All three commands in this step only **read**.

### 2a. List the GPIO controllers

```sh
gpiodetect
```

* `gpiodetect` lists every GPIO controller Linux knows about. It's part of
  **libgpiod**, the standard Linux GPIO toolkit. (OpenBMC includes libgpiod's
  command-line tools, as part of its developer tools.)
* Output format: `name [label] (number of pins)`. On our board:

  ```
  gpiochip0 [gpio-0-31] (32 lines)
  gpiochip1 [gpio-32-63] (32 lines)
  gpiochip2 [gpio-64-95] (32 lines)
  gpiochip3 [gpio-96-127] (32 lines)
  ```

* **Neither the number nor the label tells you which bank it is.** Both follow
  the order in which the banks finish starting at boot:
  * Linux gives the next free `gpiochipN` number to each bank as it starts.
  * The GPIO driver (`gpio-omap`, function `omap_gpio_chip_init()`) builds
    the label from a single counter that goes up 32 at a time as each bank
    starts. So the first bank to start is always labelled `gpio-0-31`,
    whichever bank it is.
  * On our board, **bank 1 (GPIO1, the one with the LEDs) started first**, so
    it got both `gpiochip0` **and** `gpio-0-31`. The LEDs are on
    `gpiochip0`, lines 21–24 (tested).
* **To see which hardware bank each one really is**, look at its address
  (each bank's address is fixed in the chip):

  ```sh
  for c in /sys/bus/gpio/devices/gpiochip*; do echo "$c -> $(readlink -f $c)"; done
  ```

  * `/sys/bus/gpio/devices/` has one entry per GPIO controller. Each is a
    shortcut (symbolic link) to the controller's real folder.
  * `readlink -f` prints where the shortcut really points. The folder for
    the hardware is named after the bank's address:

  | Address in the path | Bank |
  | --- | --- |
  | `44e07000.gpio` | GPIO0 |
  | `4804c000.gpio` | GPIO1 |
  | `481ac000.gpio` | GPIO2 |
  | `481ae000.gpio` | GPIO3 |

  Expected for our board: a line like
  `/sys/bus/gpio/devices/gpiochip0 -> /sys/devices/platform/…/4804c000.gpio/gpiochip0`.
  (The addresses are from the device tree. This command hasn't been run on
  the board yet.)
* In everyday use you don't need any of this: look a pin up by its name, as
  in 2b. Never hard-code `gpiochipN` in scripts.

### 2b. Look the pin up by name

```sh
gpiofind "[usr3 led]"
```

* `gpiofind` searches every controller for a pin with this name, and prints
  `<controller> <pin number>`.
* The quotes keep the space and the square brackets together as one argument.
  The name comes from the device tree (section 5.1).
* **On our board:** `gpiochip0 24`.

### 2c. Check the pin is free

```sh
gpioinfo gpiochip0 | grep led
```

* `gpioinfo gpiochip0` lists all 32 pins of that controller.
* `| grep led` keeps only the lines containing "led".
* Use whatever controller `gpiofind` printed.
* Expected (the spacing may differ):

  ```
  line  21:  "[usr0 led]"   unused   input  active-high
  line  22:  "[usr1 led]"   unused   input  active-high
  line  23:  "[usr2 led]"   unused   input  active-high
  line  24:  "[usr3 led]"   unused   input  active-high
  ```

| Column | Meaning |
| --- | --- |
| `line 24` | Pin number within this controller |
| `"[usr3 led]"` | The pin's name |
| `unused` | No program or kernel driver owns the pin. When one does, its name appears here, e.g. `"gpioset"`. |
| `input` | Current direction: `input` (not driving) or `output` (driving high or low) |
| `active-high` | 1 means 3.3 V and 0 means 0 V. (`active-low` would swap them.) |

---

## 3. Step 2: check the pin mux

Normally the LED driver would have set this pin's register to mode 7 (GPIO).
Without that driver, nobody did, so we check that it's in GPIO mode before
relying on it. There are two ways to read the register. **Both only read.**

### 3a. Through the kernel's pin-mux driver (recommended)

```sh
ls /sys/kernel/debug/pinctrl/
cat /sys/kernel/debug/pinctrl/44e10800*/pins | grep 44e10860
```

* `/sys/kernel/debug` holds debug files that the kernel creates in memory, a
  bit like `/sys`. OpenBMC mounts it at boot.
* The `pinctrl` folder has a subfolder for each pin-mux controller. The AM335x
  one is named after its address, `44e10800`. The `*` matches the rest of the
  name, whatever it is.
* The `pins` file lists every pin the controller manages: pin number, register
  address, current value.
* `grep 44e10860` keeps only our pin's line. Its value column shows
  **`00000027`** on our board.

### 3b. Straight from the hardware with `devmem`

```sh
devmem 0x44E10860 32
```

* `devmem` reads (or writes) one value at a **physical memory address**,
  bypassing every driver.
* `0x44E10860` is the register's address (section 5.2 shows how to find it).
  `32` means read 32 bits.
* **With no third argument it only reads.** Never add a value unless you know
  exactly what you're writing: writes go straight to the hardware.
* Expected on our board: `0x00000027`.

### 3c. Decoding `0x27`

`0x27` in binary is `0010 0111`. The register layout is in TI's *AM335x
Technical Reference Manual*, chapter 9, "Control Module", pad configuration
registers:

| Bits | Name | Our value | Meaning |
| --- | --- | --- | --- |
| 0–2 | MUXMODE | `111` = **7** | **Mode 7 = GPIO** (here GPIO1_24) ✅ |
| 3 | PULLUDEN | `0` | Internal pull resistor **enabled** (0 means enabled) |
| 4 | PULLTYPESEL | `0` | The pull resistor pulls **down** (1 would be up) |
| 5 | RXACTIVE | `1` | Input receiver on, so the pin's level can be read back |
| 6 | SLEWCTRL | `0` | Fast signal edges |

**What to look for:** the last hex digit must be **7** or **F** (lowest three
bits = 7). If it's anything else, the pin is set to another function and
`gpioset` won't reach the LED. See [Troubleshooting](#7-troubleshooting).

The pull-down also matters: when nobody drives the pin, it sits at 0 V, so the
LED is **off** rather than undefined.

---

## 4. Step 3: turn the LED on and off

### 4a. Turn it on

```sh
gpioset --mode=wait gpiochip0 24=1
```

| Part | Meaning |
| --- | --- |
| `gpioset` | Set output values on one or more GPIO pins (libgpiod) |
| `--mode=wait` | After setting, **keep holding the pin** until you press **Enter** |
| `gpiochip0` | The controller (from `gpiofind`) |
| `24=1` | Pin 24 = value 1 (3.3 V). Several `pin=value` pairs can be given. |

**Result (tested on our board):** USR3 lights up, and the command doesn't
return to the prompt while it holds the pin.

The same thing without typing the controller and pin yourself:

```sh
gpioset --mode=wait $(gpiofind "[usr3 led]")=1
```

`$( … )` is replaced by `gpiofind`'s output, `gpiochip0 24`, so the command
becomes `gpioset --mode=wait gpiochip0 24=1`.

### 4b. See who owns the pin (optional)

While the LED is on, open a **second** SSH session and run:

```sh
gpioinfo gpiochip0 | grep usr3
```

The line changes from `unused input` to `"gpioset" output … [used]`. The
kernel records which program owns the pin, and refuses to give it to anyone
else ("Device or resource busy") until it's released.

### 4c. Turn it off

Press **Enter** in the first session. `gpioset` exits, the kernel **releases**
the pin, and the LED goes off.

### 4d. Important: the pin is only yours while `gpioset` runs

* When a program releases a GPIO pin, this processor's GPIO driver switches the
  pin back to **input** (`omap_gpio_free()` in the kernel's `gpio-omap.c`).
* With the pull-down from section 3c, the pin then sits at 0 V and the LED goes
  off.
* That's why the default `--mode=exit`, which sets the value and exits at once,
  is useless here: the LED would be on for a moment too short to see.

| `--mode=` | Behaviour | Use |
| --- | --- | --- |
| `exit` (default) | Sets, then exits immediately, so the pin is released | Not on this chip |
| `wait` | Holds until you press Enter | Typing by hand |
| `time` | Holds for `--sec=N` and/or `--usec=N` (microseconds), then exits | Simple timed pulses |
| `signal` | Holds until it gets Ctrl-C or `kill` | Holding from a script in the background |

**To turn it off while still holding the pin** (no release in between), you'd
need one program that keeps the pin open the whole time. libgpiod 1.6's
`gpioset` can't change a value while running. See
[section 8](#8-limits-and-what-comes-next).

---

## 5. Where the numbers come from

Everything above came from three sources: the **device tree** in our image,
TI's **Technical Reference Manual** (TRM), and the BeagleBone **schematic**.
This section shows how to find the same numbers yourself, for any pin.

### 5.0 Getting the device tree

The **device tree** is a file that describes the board's hardware to Linux:
what's on the chip, at which addresses, and how pins are wired. U-Boot loads
it from `/boot` and hands it to the kernel. There are two ways to read it.

**Option A, as text on your PC (easiest to read):**

```sh
# On the Ubuntu PC:
sudo apt install device-tree-compiler
scp root@evb-beaglebone.local:/boot/am335x-boneblack.dtb .
dtc -q -I dtb -O dts -o am335x-boneblack.dts am335x-boneblack.dtb
```

* `device-tree-compiler` provides `dtc`, which converts between binary device
  trees (`.dtb`) and text (`.dts`).
* `scp … /boot/am335x-boneblack.dtb .` copies the board's device tree into
  the current folder (`.`). `/boot` is the board's FAT boot partition.
* `-q` hides warnings, `-I dtb -O dts` means binary in, text out, and `-o`
  names the output file.

Open `am335x-boneblack.dts` in any text editor. Numbers appear as `0x…`, and
links between nodes appear as number IDs called **phandles** (section 5.1b).

**Option B, live on the board (no PC tools):** the running kernel shows the
device tree it received as folders and files, in
`/sys/firmware/devicetree/base/`. Each **node** is a folder, and each
**property** is a file:

```sh
ls /sys/firmware/devicetree/base/leds/
tr '\0' '\n' < /sys/firmware/devicetree/base/leds/led5/label
xxd -g4 /sys/firmware/devicetree/base/leds/led5/gpios
```

* Text properties end with a zero byte. `tr '\0' '\n'` turns it into a newline
  so it prints neatly. Expected: `beaglebone:green:usr3`.
* Number properties are stored as 4-byte big-endian values. `xxd -g4` prints
  them in groups of 4 bytes. Expected: `00000028 00000018 00000000`.

### 5.1 From the LED to the GPIO controller and pin

**a) The LED's entry.** In the text device tree, search for `gpio-leds`:

```dts
leds {
    pinctrl-names = "default";
    pinctrl-0 = <0x63>;                      /* pin-mux settings to apply: group with ID 0x63 (5.2) */
    compatible = "gpio-leds";                /* the kernel driver meant to run these (not in our kernel) */

    led5 {
        label = "beaglebone:green:usr3";     /* the LED's name */
        gpios = <0x28 0x18 0x00>;            /* <controller ID>  <pin 0x18 = 24>  <flags 0 = active-high> */
        linux,default-trigger = "mmc1";      /* blink on eMMC activity (needs the LED driver) */
        default-state = "off";
    };
    /* led2 = usr0 (heartbeat), led3 = usr1 (mmc0), led4 = usr2 (cpu0) */
};
```

`gpios = <0x28 0x18 0x00>` says: the GPIO controller whose ID is **`0x28`**,
pin **`0x18` = 24**, flags **0** (active-high).

**b) Which controller is `0x28`?** In a device tree, a node that other nodes
point to gets a **phandle**: a number ID that other nodes use to refer to it.
Search the text for `phandle = <0x28>;`. It's inside GPIO bank 1's node:

```dts
target-module@4c000 {                       /* TI's wrapper: clock and power for this block */
    compatible = "ti,sysc-omap2", "ti,sysc";
    ranges = <0x00 0x4c000 0x1000>;          /* child address 0 = parent address 0x4c000 */

    gpio@0 {
        compatible = "ti,omap4-gpio";        /* handled by the kernel's gpio-omap driver */
        gpio-controller;                     /* this node provides GPIO pins */
        #gpio-cells = <0x02>;                /* references use 2 numbers: pin, flags */
        reg = <0x00 0x1000>;                 /* its registers: offset 0, size 4 KB */
        gpio-line-names = "P8_25 [mmc1_dat0]", ... , "[usr0 led]", "[usr1 led]",
                          "[usr2 led]", "[usr3 led]", ... ;   /* names for pins 0..31 */
        phandle = <0x28>;
    };
};
```

* The 25th entry of `gpio-line-names` (index 24) is `[usr3 led]`. That's where
  `gpiofind` gets the name from.
* On the board, the same search (tested with the image's BusyBox):

  ```sh
  for f in $(find /sys/firmware/devicetree/base -name phandle); do
      [ "$(xxd -p "$f")" = "00000028" ] && echo "${f%/phandle}"
  done
  ```

  * `find … -name phandle` lists every `phandle` file in the tree.
  * `xxd -p` prints a file's bytes as plain hex (`00000028`).
  * `${f%/phandle}` removes `/phandle` from the end, leaving the node's folder.
  * Expected:
    `/sys/firmware/devicetree/base/ocp/interconnect@48000000/segment@0/target-module@4c000/gpio@0`

**c) The controller's physical address.** A node's `reg` is relative to its
parent bus. Each parent's `ranges` converts child addresses into its own:

```
gpio@0                     reg    = <0x0 …>                     → address 0x0 inside target-module@4c000
target-module@4c000        ranges = <0x0  0x4c000 0x1000>       → 0x4c000 inside segment@0
segment@0                  ranges = <… 0x4c000 0x4c000 0x1000 …>→ 0x4c000 inside interconnect@48000000
interconnect@48000000      ranges = <0x0  0x48000000 …>          → physical address 0x4804C000
```

* So bank 1's registers start at **`0x4804C000`**. The TRM's memory map
  agrees: GPIO1 is at 0x4804_C000.
* On the board, the `readlink` loop from section 2a shows which `gpiochipN`
  sits under the folder named after this address (`4804c000.gpio`). That's
  the reliable way to match a Linux controller number to a hardware bank.

**d) Cross-check with the schematic.** The BeagleBone Black schematic shows
USR3 wired to processor pin GPMC_A8, which is GPIO1_24 in mode 7. Same answer.

### 5.2 From the LED to its pin-mux register

**a) The settings group.** The `leds` node said `pinctrl-0 = <0x63>`. Search
for `phandle = <0x63>;`:

```dts
user-leds-s0-pins {
    pinctrl-single,pins = <0x54 0x00 0x07     /* USR0: register offset 0x54, pad settings 0x00, mode 7 */
                           0x58 0x10 0x07     /* USR1: offset 0x58, settings 0x10 (pull-up),     mode 7 */
                           0x5c 0x00 0x07     /* USR2: offset 0x5c */
                           0x60 0x10 0x07>;   /* USR3: offset 0x60, settings 0x10,               mode 7 */
    phandle = <0x63>;
};
```

* Each entry is **register offset, pad settings, mode**. The kernel ORs
  (combines) the settings and the mode into one value and writes it at the
  offset.
* USR3's entry is offset **`0x60`**. This group is only written when the LED
  driver starts, and ours never does, so the register still holds its
  power-on value `0x27`.
* The device tree wants `0x10 | 0x07 = 0x17` (pull-up). Ours has `0x27`
  (pull-down, input receiver on). Both are mode 7, so either works for
  driving the LED.

**b) Offset `0x60` from what?** The group sits inside the pin-mux controller,
`pinmux@800`. Follow the `ranges` up again:

```
pinmux@800               reg    = <0x800 0x238>                → 0x800 inside scm@0
scm@0                    ranges = <0x0  0x0  0x2000>            → 0x800 inside target-module@10000
target-module@10000      ranges = <0x0  0x10000 0x10000 …>      → 0x10800 inside segment@200000
segment@200000           ranges = <… 0x10000 0x210000 0x10000 …>→ 0x210800 inside interconnect@44c00000
interconnect@44c00000    ranges = <… 0x200000 0x44e00000 …>     → physical address 0x44E10800
```

So the pin-mux registers start at **`0x44E10800`**, and USR3's register is
**`0x44E10800 + 0x60 = 0x44E10860`**. That's the address used with `devmem`
and seen in the `pinctrl` file. The controller's debug folder name
(`44e10800…`) is the same base address.

**c) Cross-check with the TRM.** The Control Module starts at `0x44E1_0000`
(TRM, chapter 2, memory map), and `conf_gpmc_a8` is at offset `0x860` (TRM,
chapter 9). 0x44E10000 + 0x860 = 0x44E10860. Same answer.

**d) Another link between GPIO and pin mux.** The bank's `gpio-ranges`
property maps GPIO pins to pin-mux registers. One of its entries,
`<0x23 0x0c 0x0c 0x10>`, means "GPIO pins 12 to 27 = pin-mux registers 12 to
27", where `0x23` is the pin-mux controller. So GPIO pin 24 uses pin-mux
register 24. Each register is 4 bytes, and 24 × 4 = 96 = `0x60`. The same
offset again.

### 5.3 Watching the GPIO registers (optional)

While `gpioset --mode=wait …24=1` holds the LED on, read bank 1's registers
from a second session. These only read:

```sh
devmem 0x4804C134 32     # OE ("output enable"): bit 24 = 0 means output, 1 means input
devmem 0x4804C13C 32     # DATAOUT: the value being driven; bit 24 = 1 means high
```

* The offsets are from the kernel's `gpio-omap` driver: `OMAP4_GPIO_OE = 0x134`
  and `OMAP4_GPIO_DATAOUT = 0x13c`.
* Bit 24 has the value `0x01000000`. In the 8-digit hex output it's the last
  bit of the **second digit from the left**:
  * `0x01000000` means bit 24 is set;
  * `0xFEFFFFFF` means bit 24 is clear.
* While the LED is on: OE bit 24 = **0** and DATAOUT bit 24 = **1**.
* After you press Enter: OE bit 24 = **1** (back to input).

---

## 6. What happens underneath

When you run `gpioset --mode=wait gpiochip0 24=1`, each layer is provided by
a different project:

| # | Layer | What it does | Provided by |
| --- | --- | --- | --- |
| 1 | `gpioset` (`/usr/bin`) | Reads your arguments | libgpiod 1.6.5 (recipe in meta-openembedded; package `libgpiod-tools`, included by OpenBMC's developer tools group) |
| 2 | `libgpiod.so.2` (`/usr/lib`) | Opens `/dev/gpiochip0` and asks the kernel for pin 24 as an output, starting at 1. It's one `ioctl()` call, using the structures in the kernel header `<linux/gpio.h>`. | libgpiod |
| 3 | C library | `open()` and `ioctl()` switch the processor from the program into the kernel | glibc |
| 4 | `gpiolib-cdev` | The kernel code behind `/dev/gpiochipN`. It handles the `ioctl()` and returns a **line handle**, a file descriptor that means "pin 24, held by you". | Linux kernel (GPIO subsystem), built by the `linux-yocto` recipe |
| 5 | `gpiolib` | Records the owner (`"gpioset"`), refuses other owners, and calls the bank's driver | Linux kernel |
| 6 | `gpio-omap` | Bank 1's driver. Switches the bank's clock on, writes bit 24 to **SETDATAOUT** (`0x4804C194`), then clears bit 24 in **OE** (`0x4804C134`). The value is written first, so the pin never briefly shows the wrong level. | Linux kernel (driver for TI's GPIO block) |
| 7 | Pad mux `0x44E10860` | Mode 7 connects the pin to GPIO1_24 | AM335x processor (Texas Instruments) |
| 8 | Pin, resistor and USR3 LED | 3.3 V on the pin lights the LED | BeagleBone Black board |

* When `gpioset` exits, the kernel closes the line handle and `gpio-omap` sets
  OE bit 24 back to 1 (input). That's why the LED goes off.
* Layers 4 and 5 are the same on every Linux system. Only layer 6 is specific
  to this processor: an Aspeed BMC chip, for example, uses `gpio-aspeed`. So
  the same commands and OpenBMC programs work on both.

---

## 7. Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| `gpiofind` prints nothing, and its exit status (`echo $?`) is non-zero | Name typed differently | The name is exactly `[usr3 led]`, with the square brackets, a space, and quotes around it. List the names with `gpioinfo \| grep led`. |
| `gpioset: error setting the GPIO line values: Device or resource busy` | Another program (or a kernel driver) owns the pin | `gpioinfo gpiochip0 \| grep usr3` shows the owner. Stop that program. With a kernel that has the LED driver, the LEDs are owned by the driver, by design. |
| `gpioset` runs, but the LED stays dark | Pin not in GPIO mode, or the wrong controller or pin | Check section 3 (last hex digit 7 or F). Re-run `gpiofind`: the controller number can change between boots. |
| LED flashes too briefly to see | `--mode=exit` (the default) | Use `--mode=wait`, `--mode=time --sec=5` or `--mode=signal` |
| `devmem: not found` | Not in this image | It's a BusyBox applet, and in our image it's present. Use the `pinctrl` file (3a) instead. |
| `/sys/kernel/debug/pinctrl` missing | Debug file system not mounted | `mount -t debugfs debugfs /sys/kernel/debug` |

**If the pin isn't in mode 7:**
* `devmem 0x44E10860 32 0x27` would write mode 7 directly. That's a raw
  hardware write that bypasses the kernel, so double-check the address first.
  It's undone by a reboot.
* The proper fix is the kernel LED driver, or a device-tree change, which set
  the pin mux at boot.

---

## 8. Limits, and what comes next

* **Why there's no LED driver.** Yocto's BeagleBone kernel settings (in the
  `yocto-kernel-cache`, `bsp/beaglebone/beaglebone.cfg`) set only
  `CONFIG_NEW_LEDS=y` and never include Yocto's ready-made `features/leds`
  feature. Adding it is one line in a kernel `.bbappend`
  (`KERNEL_FEATURES:append = " features/leds/leds.scc"`), planned for the
  next image build. After that:
  * the kernel owns the four LED pins from boot to shutdown, and sets their
    pin mux;
  * USR0 shows the heartbeat again;
  * `/sys/class/leds/` appears;
  * OpenBMC's LED programs can drive them, which is the route to the web UI's
    identify LED;
  * **`gpioset` on those pins then fails with "busy"**, by design.
* **Glitch-free control from a script or program.** `gpioset` releases the pin
  when it exits, so a script calling it repeatedly lets the pin fall back to
  input between calls. The fix is one long-running program that keeps the pin
  open and changes its value through that open handle. It can use libgpiod's C
  functions (`gpiod_line_request_output()`, `gpiod_line_set_value()`) or the
  kernel's `<linux/gpio.h>` interface directly. This is how OpenBMC's own GPIO
  programs work.
* **Other pins.** The same steps work for any pin on the P8 and P9 headers.
  Use `gpioinfo` to find its name (e.g. `P9_12`), then the device tree to find
  its pin-mux offset. For pins with an external LED, use a series resistor
  (e.g. 330 Ω to 1 kΩ). The pins are **3.3 V only** and can supply only a few
  milliamps.

---

## 9. Quick reference

```sh
gpiodetect                                   # controllers (number and label follow start-up order)
for c in /sys/bus/gpio/devices/gpiochip*; do echo "$c -> $(readlink -f $c)"; done
                                             # which hardware bank each is (address in the path)
gpiofind "[usr3 led]"                        # -> gpiochip0 24 (on our board)
gpioinfo gpiochip0 | grep led                # pin state and owner
cat /sys/kernel/debug/pinctrl/44e10800*/pins | grep 44e10860   # pin mux via the kernel
devmem 0x44E10860 32                         # pin mux straight from hardware (read only)
gpioset --mode=wait gpiochip0 24=1           # LED on until Enter
devmem 0x4804C134 32                         # GPIO1 OE      (bit 24: 0 = output)
devmem 0x4804C13C 32                         # GPIO1 DATAOUT (bit 24: 1 = high)
```

| Thing | Value | Found in |
| --- | --- | --- |
| LED | USR3, `beaglebone:green:usr3`, node `leds/led5` | Device tree |
| GPIO | Bank 1 (GPIO1), pin 24, active-high | Device tree `gpios = <0x28 0x18 0x00>` |
| GPIO1 registers | `0x4804C000` (OE `+0x134`, DATAOUT `+0x13C`, CLEARDATAOUT `+0x190`, SETDATAOUT `+0x194`) | Device tree `ranges`, TRM, `gpio-omap.c` |
| Pin-mux register | `conf_gpmc_a8`, `0x44E10860` (pin-mux base `0x44E10800` + `0x60`) | Device tree `user-leds-s0-pins`, TRM |
| Value on our board | `0x27` = mode 7 (GPIO), pull-down, input receiver on | Read with `devmem` / `pinctrl` |
| Linux controller | `gpiochip0` on our board (may differ between boots) | `gpiofind` |
