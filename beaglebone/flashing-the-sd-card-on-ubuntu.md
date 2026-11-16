# Writing the OpenBMC image to an SD card on Ubuntu

How to put the BeagleBone image on a microSD card from an Ubuntu PC, check
it, boot it, and (optionally) install it onto the board's built-in eMMC
storage afterwards. (On Windows? The balenaEtcher steps in
[README.md](README.md#9-flash-and-boot) are the Windows route.)

**Time needed:** about 10 minutes, most of it the download and the card's own
write speed.

> ⚠ **The one thing that can go wrong.** Writing an image **erases everything**
> on the disk you point it at. If you name your PC's own disk instead of the
> SD card, you erase your PC. Step 3 shows how to identify the card
> safely. Don't skip it.

The commands in this guide were tested with the released image
(`beaglebone-20261004-0244`), writing to a plain file standing in for the
card: `dd` and `bmaptool` both produced a byte-for-byte identical copy, and
`bmaptool` rejected a deliberately corrupted image. I couldn't test with a
physical card reader, and the board hasn't been booted from the card yet.

---

## What you need

* The BeagleBone Black (or a BeagleBone / BeagleBone Green: the image has
  device trees for all three).
* A **microSD card, 4 GB or bigger**, and a way to plug it into your PC: a
  USB card reader, or the PC's built-in SD slot (with a microSD-to-SD adapter).
* About 40 MB of free disk space for the download.
* `sudo` rights on the PC.

The image is small (about 173 MB once unpacked), so a 32 GB card works fine:
it simply leaves the rest of the card unused.

---

## Step 1: Download the image

Open the [Releases page](https://github.com/nimeskan/openbmc/releases), pick the
newest release, and download these three files into one folder. Or from a
terminal (this is the first release; replace the tag for a newer one):

```sh
mkdir -p ~/beaglebone-image && cd ~/beaglebone-image
B=https://github.com/nimeskan/openbmc/releases/download/beaglebone-20261004-0244
curl -L -O $B/obmc-phosphor-image-evb-beaglebone.wic.xz
curl -L -O $B/obmc-phosphor-image-evb-beaglebone.wic.bmap
curl -L -O $B/SHA256SUMS
```

| File | What it is |
| --- | --- |
| `obmc-phosphor-image-evb-beaglebone.wic.xz` | **The image** (compressed, 39.6 MB). The only file you must have. |
| `obmc-phosphor-image-evb-beaglebone.wic.bmap` | A map that lets `bmaptool` write only the parts of the card that matter (faster) and check them |
| `SHA256SUMS` | Checksums, to confirm the download isn't damaged |

## Step 2: Check the download

```sh
sha256sum -c --ignore-missing SHA256SUMS
```

You should see `OK` after each file you downloaded:

```
obmc-phosphor-image-evb-beaglebone.wic.bmap: OK
obmc-phosphor-image-evb-beaglebone.wic.xz: OK
```

If a file says `FAILED`, download it again.

## Step 3: Find the SD card's device name

This is the careful step. Linux gives each disk a name like `/dev/sdb`.
Find the card's name by **comparing the list of disks with the card out and
in**:

1. **Unplug the card** (and any other USB drives you don't need), then run:
   ```sh
   lsblk -o NAME,SIZE,TYPE,TRAN,RM,MODEL,MOUNTPOINTS
   ```
2. **Plug in the card**, wait a few seconds, run the same command again.
3. The **new** disk is your card. For example, with a **USB card reader**:
   ```
   NAME        SIZE TYPE TRAN RM MODEL        MOUNTPOINTS
   nvme0n1   476.9G disk nvme  0 Samsung SSD
   ├─nvme0n1p1 512M part       0               /boot/efi
   └─nvme0n1p2 476G part       0               /
   sdb        29.7G disk usb   1 SD/MMC       ← the new one: your card
   └─sdb1     29.7G part       1               /media/you/ABCD-1234
   ```
   or with the PC's **built-in card slot**:
   ```
   NAME          SIZE TYPE TRAN RM MODEL       MOUNTPOINTS
   nvme0n1     476.9G disk nvme  0 Samsung SSD
   ├─nvme0n1p1   512M part       0              /boot/efi
   └─nvme0n1p2   476G part       0              /
   mmcblk0      29.7G disk       0             ← the new one: your card
   └─mmcblk0p1  29.7G part       0              /media/you/ABCD-1234
   ```
   Here the card is **`/dev/sdb`** (USB reader) or **`/dev/mmcblk0`**
   (built-in slot). Check that the **size matches your card** and that it is
   **not** the disk with `/` or `/boot/efi` in the MOUNTPOINTS column. (For a
   built-in slot, the TRAN column is usually empty and RM may show `0` or `1`.)

How to recognise it:

* A card in a **USB reader** appears as `sdb`, `sdc`, … with `TRAN` = `usb`
  and `RM` (removable) = `1`.
* A card in the PC's **built-in slot** usually appears as `/dev/mmcblk0`
  (partitions `mmcblk0p1`, …). Careful: on some laptops `mmcblk0` is the
  *internal* storage. Check the size and the mount points.
* Never use a name that has a number on the end (`sdb1`) or a `p` + number
  (`mmcblk0p1`): those are partitions. Use the whole disk (`sdb`, `mmcblk0`).

Below, every command is shown twice. **Use the line for your setup** and
replace the placeholder with your card's name from above:

| Your card is in | Placeholder | Replace with, for example | Its partitions |
| --- | --- | --- | --- |
| A USB card reader | `/dev/sdX` | `/dev/sdb` | `sdb1`, `sdb2` |
| The PC's built-in slot | `/dev/mmcblkN` | `/dev/mmcblk0` | `mmcblk0p1`, `mmcblk0p2` (note the `p`) |

> ⚠ **`X` and `N` are placeholders. Don't type them.** Replace the capital
> **`X`** with your card's letter (`/dev/sdX` → `/dev/sdb`) and the capital
> **`N`** with your card's number (`/dev/mmcblkN` → `/dev/mmcblk0`, and
> `/dev/mmcblkNp*` → `/dev/mmcblk0p*`), using the name you found in step 3.
> If you run a command with the letter `N` or `X` left in, it won't write to
> your card: `dd` would instead create an ordinary file called `/dev/mmcblkN`
> and seem to succeed. If that happened, delete that file with
> `sudo rm /dev/mmcblkN` (or `/dev/sdX`) and run the command again with the
> right name.

## Step 4: Unmount the card

Ubuntu usually mounts a card's partitions automatically. Unmount them first:

```sh
# USB card reader (replace X with your letter, e.g. sdX -> sdb):
sudo umount /dev/sdX?*

# Built-in card slot (replace N with your number, e.g. mmcblkN -> mmcblk0):
sudo umount /dev/mmcblkNp*
```

Errors such as `not mounted` are fine.

## Step 5: Write the image

Pick **one** of these methods.

### Method A: `bmaptool` (recommended)

Faster (it writes only the parts that hold data, about half the image), and it
checks every block against checksums stored in the `.bmap` file. Install it
once:

```sh
sudo apt install bmap-tools
```

Then, in the folder with the downloaded files:

```sh
cd ~/beaglebone-image

# USB card reader (replace X with your letter, e.g. sdX -> sdb):
sudo bmaptool copy obmc-phosphor-image-evb-beaglebone.wic.xz /dev/sdX

# Built-in card slot (replace N with your number, e.g. mmcblkN -> mmcblk0):
sudo bmaptool copy obmc-phosphor-image-evb-beaglebone.wic.xz /dev/mmcblkN
```

`bmaptool` finds the `.bmap` file by itself when it sits next to the image
with the matching name (it says `discovered bmap file …`). If you see
`bmaptool: ERROR: checksum mismatch`, the image is damaged: download it again.

### Method B: `dd` (works everywhere, nothing to install)

```sh
cd ~/beaglebone-image

# USB card reader (replace X with your letter, e.g. sdX -> sdb):
xzcat obmc-phosphor-image-evb-beaglebone.wic.xz | \
  sudo dd of=/dev/sdX bs=4M conv=fsync status=progress

# Built-in card slot (replace N with your number, e.g. mmcblkN -> mmcblk0):
xzcat obmc-phosphor-image-evb-beaglebone.wic.xz | \
  sudo dd of=/dev/mmcblkN bs=4M conv=fsync status=progress
```

This unpacks the image on the fly and writes all of it. It prints progress and
finishes with something like `181611520 bytes (182 MB, 173 MiB) copied`.
`dd` doesn't ask for confirmation and doesn't check the result.

### Method C: balenaEtcher (graphical)

Download Etcher from [etcher.balena.io](https://etcher.balena.io/), choose
**Flash from file** → the `.wic.xz` file (no need to unpack it) → **Select
target** → your card → **Flash!** It checks the card afterwards. I haven't
tested Etcher on Ubuntu; if it won't start, use method A or B.

## Step 6: Finish and remove the card

```sh
# USB card reader (replace X with your letter, e.g. sdX -> sdb):
sync
sudo udisksctl power-off -b /dev/sdX

# Built-in card slot (replace N with your number, e.g. mmcblkN -> mmcblk0):
sync
sudo umount /dev/mmcblkNp*      # in case Ubuntu mounted the new partitions
```

`sync` makes sure everything has really been written. For a USB reader,
`udisksctl power-off` detaches the reader so it's safe to pull out. A
built-in slot usually can't be "powered off" (`udisksctl` may refuse), so
there, once it's synced and unmounted, you can simply take the card out. (Or,
either way: right-click the card in the Files app → **Eject** / **Safely
Remove Drive**.)

To double-check, put the card back in (Ubuntu may mount it again; that's
fine) and run:

```sh
# USB card reader (replace X with your letter, e.g. sdX -> sdb):
lsblk -o NAME,SIZE,FSTYPE,LABEL /dev/sdX

# Built-in card slot (replace N with your number, e.g. mmcblkN -> mmcblk0):
lsblk -o NAME,SIZE,FSTYPE,LABEL /dev/mmcblkN
```

You should see two partitions:

```
# USB card reader:
NAME    SIZE FSTYPE LABEL
sdb    29.7G
├─sdb1    32M vfat   boot
└─sdb2 141.2M ext4   root

# Built-in card slot:
NAME          SIZE FSTYPE LABEL
mmcblk0      29.7G
├─mmcblk0p1    32M vfat   boot
└─mmcblk0p2 141.2M ext4   root
```

Unmount and remove it again before putting it in the BeagleBone.

That's right: the image only uses about 173 MB, so a big card shows a small
`root` partition and the rest unused. It does not mean the write failed.

## Step 7: First boot

1. Make sure the BeagleBone is **powered off**. Insert the card.
2. **Hold the S2 button** (small, near the microSD slot), plug in power, and
   release S2 when the blue LEDs start blinking. Holding S2 tells the board to
   boot from the card instead of its built-in storage.
3. Connect to it: the [Ubuntu connection guide](connecting-from-an-ubuntu-pc.md)
   covers the serial terminal, a direct Ethernet cable, the web UI, Redfish and
   SSH. Log in as `root` / `0penBmc`.

If you re-flash a card and then see an SSH "REMOTE HOST IDENTIFICATION HAS
CHANGED" warning, that's expected: see the SSH section of that guide.

---

## Optional: install to the board's built-in eMMC

The BeagleBone Black has 4 GB of built-in eMMC storage (it usually ships with a
Debian system on it). Once the card works, you can copy OpenBMC there, so the
board boots without a card.

> ⚠ This **erases the eMMC**, including the Debian system it came with.
> (To go back to that later you'd flash BeagleBoard.org's own image.) The SD
> card is untouched.

1. Boot from the card (step 7).
2. **Set up the network link between your PC and the board first.** The next
   steps use `scp` and `ssh`, which work over Ethernet only; a UART (serial)
   connection alone isn't enough. Follow section B of the
   [Ubuntu connection guide](connecting-from-an-ubuntu-pc.md#b-direct-ethernet-cable-ubuntu--beaglebone-no-router)
   ("Shared to other computers" is the easiest), then check that
   `ssh root@evb-beaglebone.local` logs you in. The setup is saved on your PC,
   so after switching to the eMMC you only run `nmcli connection up beaglebone`
   again.
3. From your PC, copy the image to the board's `/tmp`:
   ```sh
   scp ~/beaglebone-image/obmc-phosphor-image-evb-beaglebone.wic.xz \
       root@evb-beaglebone.local:/tmp/
   ```
   (`scp`, `xzcat` and `dd` are all in the image, which I checked. The image is
   about 40 MB; the board's root partition has about 55 MB free, which is
   enough.)
4. Log in to the board: `ssh root@evb-beaglebone.local`.
5. **Confirm which device is the eMMC** before writing anything. These
   `mmcblk` names are the **board's** names, unrelated to what your PC called
   the card. On the board, the card is `mmcblk0` and the eMMC is `mmcblk1`:
   ```sh
   cat /proc/partitions
   ```
   `mmcblk1` should be about 3.6–3.7 GB (a "4 GB" part; very old boards have
   2 GB) and may be followed by small `mmcblk1boot0` / `mmcblk1boot1` entries.
   `mmcblk0` is your card (its size, with `mmcblk0p1` and `mmcblk0p2`). If the
   sizes don't match that, stop and ask. The board has no `lsblk`, so use
   this command.
6. Write it:
   ```sh
   xzcat /tmp/obmc-phosphor-image-evb-beaglebone.wic.xz | dd of=/dev/mmcblk1 bs=4M conv=fsync
   sync
   poweroff
   ```
7. When the LEDs go out, **remove the SD card** and power the board on
   **without** holding S2. It now boots from the eMMC.

---

## Troubleshooting

| Problem | What to try |
| --- | --- |
| `Permission denied` | Put `sudo` in front of the command that writes to `/dev/…` |
| `Device or resource busy` / `is mounted` | The card is still mounted: repeat step 4 (`sudo umount /dev/sdX?*`, or `sudo umount /dev/mmcblkNp*` for the built-in slot) |
| `No such file or directory` on `/dev/sdX` or `/dev/mmcblkN` | The name is wrong or the card isn't detected: redo step 3; try another USB port or reader, or re-seat the card in the slot; `sudo dmesg \| tail` shows what Linux saw |
| Built-in slot: you used `/dev/mmcblk0p1` and the board doesn't boot | You wrote to a partition, not the whole card. Write again to `/dev/mmcblk0` (no `p1`) |
| `udisksctl power-off` fails for the built-in slot | Normal for many built-in slots: after `sync` and `umount`, just remove the card |
| The card doesn't appear in `lsblk` at all | Try another reader or card. If it's an SD adapter, check the **write-protect (lock) switch** on its side |
| `Read-only file system` / write errors | Same: the adapter's lock switch is on, or the card is failing. Try another card |
| `bmaptool: ERROR: bmap file not found` | The `.bmap` file must be in the same folder and named like the image, or add `--bmap obmc-phosphor-image-evb-beaglebone.wic.bmap` |
| `bmaptool: ERROR: checksum mismatch` | The image is damaged: download again, run step 2 |
| `xzcat: command not found` | `sudo apt install xz-utils` |
| `dd` finishes but the board doesn't boot | Did you hold **S2** while powering on? Re-flash with method A (it checks the data). Watch the boot on the serial terminal ([Ubuntu connection guide](connecting-from-an-ubuntu-pc.md#a-serial-terminal-no-network-at-all)) |
| After flashing, Ubuntu pops up two new drives | Normal: those are the card's `boot` and `root` partitions. Eject before removing the card |
| Wrote to the wrong disk | There's no undo for that. This is why step 3 exists |
