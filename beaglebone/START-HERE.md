# Start here: what to read, and in what order

This folder has several documents. This page tells you which to read first,
what each one is for, and what you can leave for later.

## Read these, in this order

### 1. Connecting from a Windows PC: [`connecting-from-a-windows-pc.md`](connecting-from-a-windows-pc.md)

* The shortest and most practical. Read it first, because it's what you'll
  use at your first boot.
* Covers the serial terminal with PuTTY, connecting with **one Ethernet cable
  and no router**, and using the web UI, Redfish and SSH from Windows.

### 2. Main BeagleBone guide: [`README.md`](README.md)

The long one. Read it in this order:

| Section | What it gives you | When |
| --- | --- | --- |
| [1. The short version](README.md#1-the-short-version) and [9. Flash and boot](README.md#9-flash-and-boot) | Getting the board running | First |
| [2. Background](README.md#2-background-the-words-you-need) | A glossary of Yocto and OpenBMC terms | Keep it handy |
| [3–8](README.md#3-the-big-picture) | How it all works: layers, how the build works, the cloud build, what's in the image | When you want to understand it |
| [4. What was done, step by step](README.md#4-what-was-done-step-by-step) | The full record of everything that was done, including the problems along the way | When reviewing |

When reviewing, check that what it says was done matches what you expected.

### 3. Redfish and I2C sensor guide: [`redfish-i2c-sensor/README.md`](redfish-i2c-sensor/README.md)

* Read it after the board boots. It's background and a plan for the future,
  not something you need yet.
* **Sections 1–3:** what Redfish is and how to use it.
* **Section 4:** how OpenBMC handles sensors, and its two "sensor stacks".
* **Sections 5–9:** adding an example I2C sensor and watching it.
* **Section 10:** the no-code route with a real TMP75/LM75 chip.
* **Nothing in it is applied to your build.** The example files in its
  `files/` folder only take effect if you copy them in.

## Skim or keep for later

| File | What it is | When |
| --- | --- | --- |
| [`build-beaglebone.sh`](build-beaglebone.sh) | The commented script for building on your own Linux PC | When you get a Linux machine |
| [`../meta-evb/meta-evb-beaglebone/`](../meta-evb/meta-evb-beaglebone/) | The 6 small files that are the BeagleBone support itself. `conf/machine/evb-beaglebone.conf` is the most important (about 20 lines). | Worth a look: this is the only part that actually goes into the image |
| [`../.github/workflows/build-beaglebone.yml`](../.github/workflows/build-beaglebone.yml) | The cloud build recipe | Only if you want to understand or change the automatic build |

## Not a document, but your result

**The image:** release
[`beaglebone-20261004-0244`](https://github.com/nimeskan/openbmc/releases/tag/beaglebone-20261004-0244).
Download `obmc-phosphor-image-evb-beaglebone.wic.xz` and write it to a
microSD card with [balenaEtcher](https://etcher.balena.io/).

## What in this repository differs from official OpenBMC

No official OpenBMC file was modified or deleted. Everything was **added**:

| Added | Part of the image? |
| --- | --- |
| `meta-evb/meta-evb-beaglebone/`: the BeagleBone board support | Yes |
| `upstream-layers/meta-yocto/` (+ the `meta-yocto-bsp` shortcut): Yocto's official BeagleBone files, copied in | Yes |
| `.github/workflows/build-beaglebone.yml`: the cloud build | No, it runs the build |
| `beaglebone/`: these documents, diagrams, the build script and example files | No |
