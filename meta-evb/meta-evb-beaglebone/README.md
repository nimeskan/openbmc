# OpenBMC on BeagleBone Black

This layer adds the `evb-beaglebone` machine: OpenBMC running on a TI AM335x
BeagleBone Black (and BeagleBone / BeagleBone Green), booting from an SD card
or the onboard eMMC.

It reuses the Yocto reference BSP (`beaglebone-yocto` from `meta-yocto-bsp`)
for the kernel, U-Boot, device trees and SD card layout, and builds the
standard `obmc-phosphor-image` on top of it.

**New to this?** The full beginner's guide, with diagrams and a local build
script, is in [`beaglebone/`](../../beaglebone/README.md).

## What works / what doesn't

The BeagleBone is not a server BMC chip, so there is no host-facing hardware
(LPC/eSPI, KCS, PECI, KVM, host UART). Everything else in the OpenBMC stack
runs: bmcweb (Redfish + web UI), IPMI over LAN, user management, logging, and
sensors/fans/GPIOs you attach over I2C or the headers.

The root filesystem is a plain read-write ext4 partition. OpenBMC's A/B
firmware update flow is not set up; update by rewriting the SD card.

## Get a prebuilt image

The `Build BeagleBone Black image` GitHub Actions workflow
(`.github/workflows/build-beaglebone.yml`) builds the image and attaches it to
a GitHub Release. Start it from the repository's **Actions** tab. A full build
takes longer than one job may run, so the workflow resumes itself in follow-up
runs until the image is done. Download the `.wic.xz` file from **Releases**.

## Build

```sh
. setup evb-beaglebone
bitbake obmc-phosphor-image
```

The image is written to
`tmp/deploy/images/evb-beaglebone/obmc-phosphor-image-evb-beaglebone.rootfs.wic.xz`.
`rm_work` is enabled in the template `local.conf` to keep disk usage down.

## Flash to an SD card

Use [balenaEtcher](https://etcher.balena.io/) (Windows, macOS, Linux): pick
the `.wic.xz` file and the SD card; it decompresses on the fly.

On Linux you can also use:

```sh
xzcat obmc-phosphor-image-evb-beaglebone.rootfs.wic.xz | sudo dd of=/dev/sdX bs=4M conv=fsync
```

## Boot

1. Insert the SD card with the board powered off.
2. Hold the **S2 (BOOT)** button (near the SD slot), apply power, release
   after the LEDs start blinking. This forces boot from SD instead of eMMC.
3. Connect Ethernet. The board requests an address over DHCP.
4. Open `https://<board-ip>/` and log in as `root` / `0penBmc`.

A 3.3 V USB serial cable on header J1 (115200 8N1) gives you the console.

## Install to eMMC

Boot from SD, copy the `.wic.xz` file to the board (e.g. with `scp`), then:

```sh
xzcat obmc-phosphor-image-evb-beaglebone.rootfs.wic.xz | dd of=/dev/mmcblk1 bs=4M conv=fsync
```

Power off, remove the SD card, and power on without holding S2.
