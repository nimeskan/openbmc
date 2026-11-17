# Adding a data partition to the BeagleBone's eMMC

How to turn the unused part of the BeagleBone Black's built-in eMMC (about
3.4 GB) into a separate **ext4 data partition**, mounted at **`/data`**, for
your own files (git repos, logs, test data…), without touching the running
OpenBMC system.

**Before you start, you need:**

* The board **running OpenBMC from the eMMC** (installed as in
  [flashing-the-sd-card-on-ubuntu.md](flashing-the-sd-card-on-ubuntu.md#optional-install-to-the-boards-built-in-emmc)),
  with **no SD card inserted**.
* **SSH working** from your Ubuntu PC
  ([connecting-from-an-ubuntu-pc.md](connecting-from-an-ubuntu-pc.md#b-direct-ethernet-cable-ubuntu--beaglebone-no-router)).
* On the PC, the folder `~/beaglebone-image` with the image file you flashed,
  `obmc-phosphor-image-evb-beaglebone.wic.xz`.
* The **SD card with OpenBMC on it**, kept nearby: it's your way back if
  something goes wrong (see [If something goes wrong](#if-something-goes-wrong)).
* About 15 minutes.

> **How this was tested.** After writing this page, every command block below
> was extracted from the page itself and run in order: the PC parts with
> Ubuntu's tools, the board parts with **the board's own BusyBox** (taken from
> the released image, run in an ARM emulator) on a real block device exactly
> the size of the board's eMMC with the image written to it. Result: the new
> partition appeared, the data partition checked clean, mounted and accepted
> files, and the existing boot and root partitions were byte-for-byte
> unchanged. The [re-flash recovery](#after-re-flashing-the-emmc) was tested
> the same way: after re-writing the image, `/data` disappeared; after
> restoring the table, it came back with its files intact. It hasn't been run
> on a physical board yet.

---

## Contents

1. [The idea in one minute](#the-idea-in-one-minute)
2. [Before and after](#before-and-after)
3. [Part 1: On the board, check the starting point](#part-1-on-the-board-check-the-starting-point)
4. [Part 2: On the PC, prepare the two files](#part-2-on-the-pc-prepare-the-two-files)
5. [Part 3: On the board, write the new partition table and reboot](#part-3-on-the-board-write-the-new-partition-table-and-reboot)
6. [Part 4: On the board, put the filesystem in and mount it](#part-4-on-the-board-put-the-filesystem-in-and-mount-it)
7. [Using it](#using-it)
8. [If something goes wrong](#if-something-goes-wrong)
9. [After re-flashing the eMMC](#after-re-flashing-the-emmc)
10. [Troubleshooting](#troubleshooting)

---

## The idea in one minute

A disk has a **partition table** (a small list at the very start of the disk,
in sector 0, saying where each partition begins and ends) and, inside each
partition, a **filesystem** (the structure that organises files and folders).

The eMMC's table currently lists two partitions, `boot` and `root`. The rest
of the eMMC isn't listed, so nothing can use it. To make it usable we need to:

1. **Add a third entry to the partition table** ("partition 3 runs from here
   to the end of the disk").
2. **Put an empty ext4 filesystem inside that new partition.**
3. **Mount it** at a folder, `/data`, so its files appear there.

The board can't do steps 1 and 2 well on its own: its `fdisk` is a small
BusyBox version and it has no `mkfs.ext4`. So:

* Your **Ubuntu PC** builds the new partition table and the empty filesystem
  as two small files, using its full tools, where you can check them.
* The **board** only copies them into place with `dd` (which copies bytes
  exactly) and mounts the result.

Why it's safe for the running system:

* The new partition table is identical to the current one except for the
  added entry 3: the entries for `boot` and `root` don't change by one byte.
* A checksum check makes sure you're editing exactly the table you expect.
* The filesystem is written **into partition 3's own device**
  (`/dev/mmcblk1p3`), which ends where partition 3 ends: even a typo can't make
  it overwrite `boot` or `root`.

The one step that touches the running disk's structure is writing the new
table (512 bytes). If that went wrong the board might not boot from the eMMC,
and you'd recover with the SD card ([below](#if-something-goes-wrong)).

## Before and after

All positions are in **sectors** (512-byte blocks, the eMMC's unit).

```
BEFORE  ┌─────┬───────────────┬────────────────────┬────────────────────────────────────────┐
        │ MBR │ p1 boot 32 MiB│ p2 root 141.2 MiB  │ unused, ≈ 3.4 GiB                      │
        └─────┴───────────────┴────────────────────┴────────────────────────────────────────┘
          0     8 … 65,543      65,544 … 354,709     354,710 … end

AFTER   ┌─────┬───────────────┬────────────────────┬─┬──────────────────────────────────────┐
        │ MBR*│ p1 boot 32 MiB│ p2 root 141.2 MiB  │ │ p3 data, ext4, ≈ 3.4 GiB → /data    │
        └─────┴───────────────┴────────────────────┴─┴──────────────────────────────────────┘
          0     8 … 65,543      65,544 … 354,709      356,352 … end
        * table now also lists p3        tiny gap (0.8 MiB): p3 starts on a 1 MiB boundary
```

Partition 3 starts at sector **356,352** (exactly 174 MiB), just after
`root`, rounded up to the next 1 MiB boundary as disk tools normally do. It
runs to the last sector of the eMMC.

---

## Part 1: On the board, check the starting point

<!-- test: board -->
```sh
ls /dev/mmcblk0 2>/dev/null || echo "No SD card: good"
cat /sys/block/mmcblk1/size
```

**Run on: BeagleBone** (SSH). What these do:

* `ls /dev/mmcblk0 …`: `mmcblk0` is the SD card slot. If a card is inserted
  this prints `/dev/mmcblk0`: **power off, remove the card, boot again**. (With
  the SD card in, the board could even be running the card's copy of the
  system.) With no card it prints `No SD card: good`.
* `cat /sys/block/mmcblk1/size`: the eMMC's size in sectors. The Linux kernel
  publishes it in this file. **Write the number down**: Part 2 needs it.
  On a 4 GB BeagleBone Black it's typically `7471104` (3.56 GiB).

---

## Part 2: On the PC, prepare the two files

**Run on: Ubuntu PC**, in **one terminal window** from start to end of this
part: the first block sets variables that the later blocks use.

### 2.1 Set the numbers

<!-- test: pc -->
```sh
cd ~/beaglebone-image
EMMC_SECTORS=7471104                   # the number from Part 1 (replace if yours differs)
P3_START=356352                        # where partition 3 starts: 174 MiB
P3_SIZE=$((EMMC_SECTORS - P3_START))   # from there to the end of the eMMC
echo "Partition 3: start $P3_START, size $P3_SIZE sectors"
```

* `cd ~/beaglebone-image`: go to the folder with the image file.
* `EMMC_SECTORS=…`, `P3_START=…`: store numbers in shell variables (names
  you can reuse below as `$EMMC_SECTORS` and so on). Use **your** number from
  Part 1 for `EMMC_SECTORS`.
* `P3_SIZE=$((…))`: `$(( ))` does arithmetic. Partition 3's size is "from its
  start to the end".
* For the typical board this prints `start 356352, size 7114752 sectors`.

### 2.2 Get the current partition table

<!-- test: pc -->
```sh
xzcat obmc-phosphor-image-evb-beaglebone.wic.xz | head -c 512 > mbr-old.bin
```

* `xzcat …`: unpacks the image and streams it out.
* `| head -c 512`: keeps only the first 512 bytes (sector 0), which is the
  partition table. `head` then stops, so this is quick.
* `> mbr-old.bin`: saves it in a file. Because the eMMC was written from this
  image, this is exactly what's in the eMMC's sector 0 now (Part 3 checks
  that).

### 2.3 Build the new partition table

<!-- test: pc -->
```sh
cp mbr-old.bin disk-layout.img
truncate -s $((EMMC_SECTORS * 512)) disk-layout.img
echo "start=$P3_START, size=$P3_SIZE, type=83" | sfdisk --append disk-layout.img
sfdisk -l disk-layout.img
head -c 512 disk-layout.img > mbr-new.bin
rm disk-layout.img
```

* `cp … disk-layout.img` and `truncate -s …`: make a stand-in "disk" file with
  the current table at the start and exactly the eMMC's size. `truncate`
  makes it a *sparse* file: it reports 3.56 GiB but takes almost no real disk
  space.
* `echo "start=…" | sfdisk --append disk-layout.img`: `sfdisk` is Ubuntu's
  scriptable partitioning tool. `--append` adds one partition after the
  existing ones and **leaves them unchanged**. `type=83` is the standard type
  code for a Linux partition.
* `sfdisk -l disk-layout.img`: **check the result.** It must list:
  ```
  Device           Boot  Start     End Sectors   Size Id Type
  disk-layout.img1 *         8   65543   65536    32M  c W95 FAT32 (LBA)
  disk-layout.img2       65544  354709  289166 141.2M 83 Linux
  disk-layout.img3      356352 7471103 7114752   3.4G 83 Linux
  ```
  Partitions 1 and 2 exactly as before; partition 3 new. (On a board with a
  different eMMC size, the end and size of partition 3 differ.)
* `head -c 512 … > mbr-new.bin`: save the new sector 0 (the new partition
  table) as a file.
* `rm disk-layout.img`: the stand-in isn't needed any more.

### 2.4 Make the empty ext4 filesystem

<!-- test: pc -->
```sh
truncate -s $((P3_SIZE * 512)) data.ext4
mkfs.ext4 -L data -m 0 data.ext4
xz -T0 data.ext4
ls -l mbr-old.bin mbr-new.bin data.ext4.xz
```

* `truncate -s …`: an empty (sparse) file exactly partition 3's size.
* `mkfs.ext4 -L data -m 0 data.ext4`: **creates the ext4 filesystem** inside
  that file.
  * `-L data` gives it the name ("label") `data`.
  * `-m 0` reserves no space for the administrator. By default ext4 keeps 5%
    back so a full *system* disk can still be repaired; on a pure data
    partition that would just waste about 170 MB.
* `xz -T0 data.ext4`: compresses it (`-T0` = use all CPU cores) into
  `data.ext4.xz` and removes the original. It's almost all empty space, so
  3.4 GB becomes about **550 KB**. Takes about 10–30 seconds.
* `ls -l …`: shows the three files: `mbr-old.bin` and `mbr-new.bin` (512 bytes
  each) and `data.ext4.xz` (about 550 KB).

### 2.5 Copy the files to the board

<!-- test: pc -->
```sh
scp mbr-old.bin mbr-new.bin data.ext4.xz root@evb-beaglebone.local:
```

* `scp`: copies over SSH. The `:` at the end with nothing after it means
  "root's home folder on the board" (`/home/root`).
* Not `/tmp/`: on the board, `/tmp` is kept in memory and is **emptied at the
  reboot** in Part 3. The home folder survives.

**Keep these three files on your PC.** `mbr-new.bin` is what brings `/data`
back after a future re-flash ([see below](#after-re-flashing-the-emmc)), and
`mbr-old.bin` undoes the change.

---

## Part 3: On the board, write the new partition table and reboot

**Run on: BeagleBone** (SSH: `ssh root@evb-beaglebone.local`).

### 3.1 Safety check

<!-- test: board -->
```sh
dd if=/dev/mmcblk1 bs=512 count=1 | md5sum
md5sum < ~/mbr-old.bin
```

* The first line reads the eMMC's current sector 0 (its partition table) and
  prints its checksum; `bs=512 count=1` = one block of 512 bytes.
* The second prints the checksum of `mbr-old.bin` (the table Part 2 started from).
* **The two checksums must be identical.** Then the eMMC holds exactly the
  table the new one was built from. **If they differ, stop**: the eMMC isn't in
  the expected state (for example, it was flashed from a different image), and
  the new table would be wrong for it.

### 3.2 Write the new table

<!-- test: board -->
```sh
dd if=~/mbr-new.bin of=/dev/mmcblk1 bs=512 count=1
sync
```

* `dd if=… of=/dev/mmcblk1 bs=512 count=1`: copies the 512-byte new table onto
  sector 0 of the eMMC. It prints `1+0 records out`. Partitions 1 and 2 keep
  exactly the same entries, so nothing changes for the running system.
* `sync`: makes sure it's really written to the chip.

### 3.3 Reboot

<!-- test: board-reboot -->
```sh
reboot
```

Linux reads a disk's partition table when it starts, and won't re-read it
for the disk it's running from. The reboot makes it notice partition 3.

Your SSH session ends. Wait about a minute, then **on the PC**:

```sh
nmcli connection up beaglebone
ssh root@evb-beaglebone.local
```

If the board doesn't come back, see [If something goes wrong](#if-something-goes-wrong).

---

## Part 4: On the board, put the filesystem in and mount it

**Run on: BeagleBone** (SSH).

### 4.1 Check partition 3 exists

<!-- test: board -->
```sh
grep mmcblk1 /proc/partitions
```

`/proc/partitions` lists every disk and partition the kernel knows, with sizes
in KB. You should now see **`mmcblk1p3`**, about `3557376` KB on a typical
board, next to `mmcblk1p1` (`32768`) and `mmcblk1p2` (`144583`). If
`mmcblk1p3` is missing, **stop** and see [Troubleshooting](#troubleshooting).

### 4.2 Write the empty filesystem into partition 3

<!-- test: board -->
```sh
xzcat ~/data.ext4.xz | dd of=/dev/mmcblk1p3 bs=1M
sync
```

* `xzcat ~/data.ext4.xz`: unpacks the filesystem (3.4 GB, mostly zeros).
* `| dd of=/dev/mmcblk1p3 bs=1M`: writes it into **partition 3's own device**,
  1 MiB at a time. It can't write outside partition 3.
* Takes a few minutes. It ends with a line like `0+NNNNNN records out`; the
  `0+` is normal when `dd` reads from a pipe.
* The board's `dd` is BusyBox's: don't add `conv=fsync` (BusyBox rejects it);
  the `sync` afterwards does that job.

### 4.3 Mount it at `/data`

<!-- test: board -->
```sh
mkdir -p /data
mount /dev/mmcblk1p3 /data
df -h /data
```

* `mkdir -p /data`: creates the empty folder where the partition's contents
  will appear (`-p`: no error if it already exists).
* `mount /dev/mmcblk1p3 /data`: attaches partition 3 at `/data`. From now on,
  anything written under `/data` goes onto partition 3.
* `df -h /data`: shows its size and free space in human-readable units,
  about `3.3G` size with `3.2G` available on a typical board (ext4 uses a
  little of the space for its own bookkeeping).

### 4.4 Mount it automatically at every boot

<!-- test: board -->
```sh
echo '/dev/mmcblk1p3  /data  ext4  defaults,nofail  0  0' >> /etc/fstab
cat /etc/fstab
```

* `/etc/fstab` is the list of filesystems Linux mounts at boot. `>>` **adds**
  a line at the end (a single `>` would overwrite the whole file, so check you
  typed two).
* The fields: the partition, the folder, the filesystem type, options, and
  two zeros.
  * `defaults`: normal read-write mounting.
  * `nofail`: if partition 3 is ever missing (for example after a re-flash),
    the board still boots normally instead of stopping.
  * The last `0`: don't run a disk check at boot. The board has no ext4 check
    tool (`e2fsck`).
* `cat /etc/fstab`: shows the file, so you can see the new last line.

### 4.5 Try it, and tidy up

<!-- test: board -->
```sh
echo "hello from /data" > /data/hello.txt
cat /data/hello.txt
rm ~/data.ext4.xz ~/mbr-old.bin ~/mbr-new.bin
```

* Writes a small file to `/data` and reads it back.
* Removes the copies on the board (the originals stay on your PC).

**Optional:** `reboot`, reconnect, and run `df -h /data` again to see it
mounted automatically.

---

## Using it

* Your space is **`/data`**, about 3.3 GB, with room for about 220,000 files
  (the root filesystem only has about 15,000 free file slots).
* Copy things from the PC with `scp` or `rsync`, for example
  `rsync -a ~/myrepo/ root@evb-beaglebone.local:/data/myrepo/`.
* The board has no `git` command (see the
  [description of tools](description-of-tools.md) and earlier notes); files
  copied in, including a repo's `.git` folder, are stored fine.
* Everything outside `/data` (the OpenBMC system on `root`) is unchanged.

---

## If something goes wrong

**The board doesn't come back after the reboot in Part 3.** Watch the serial
terminal to see where it stops. To recover:

1. Power off. Insert the SD card with OpenBMC. **Hold S2** and power on: the
   board boots from the SD card.
2. Connect (SSH) as usual. While booted from the card, the eMMC is still
   `mmcblk1`.
3. Copy `mbr-old.bin` from the PC
   (`scp mbr-old.bin root@evb-beaglebone.local:`) and put the old table back:
   ```sh
   dd if=~/mbr-old.bin of=/dev/mmcblk1 bs=512 count=1
   sync
   poweroff
   ```
4. Remove the SD card and power on: the eMMC is back to how it was.

Or re-flash the eMMC completely, as in the
[flashing guide](flashing-the-sd-card-on-ubuntu.md#optional-install-to-the-boards-built-in-emmc).

**Part 4 went wrong** (for example the `dd` was interrupted). Only partition
3 is affected; the system runs normally. Just repeat Part 4 from 4.2 (copy
`data.ext4.xz` to the board again first).

---

## After re-flashing the eMMC

Re-flashing writes the image's own partition table, which doesn't list
partition 3, so **`/data` disappears**, and the `/etc/fstab` line is gone
too (it lived on the old `root`). **The data itself is still there** in that
area of the eMMC, as long as the image you flashed ends before sector 356,352.

To get it back after re-flashing the **same image**:

1. Copy your saved `mbr-old.bin` and `mbr-new.bin` from the PC to the board
   again (`scp mbr-old.bin mbr-new.bin root@evb-beaglebone.local:`, run in
   `~/beaglebone-image`), then do **Part 3** again (safety check, write the
   table, reboot).
2. In Part 4, do **only 4.1, 4.3 and 4.4**. **Skip 4.2**: writing
   `data.ext4.xz` again would replace your data with an empty filesystem.

After flashing a **different (newer) image**, the `root` partition may be a
different size, so `mbr-new.bin` must be rebuilt from that image (repeat
Part 2.2 and 2.3 with the new image file), and check that the new `root` still
ends before sector 356,352.

---

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Part 1 prints `/dev/mmcblk0` | An SD card is inserted. Power off, remove it, boot again |
| Part 1's number isn't `7471104` | Normal for some boards. Use your number for `EMMC_SECTORS` in Part 2 |
| `sfdisk -l` in 2.3 doesn't show partitions 1 and 2 as listed | Stop. `mbr-old.bin` didn't come from the right image; check you're in `~/beaglebone-image` with the image you flashed |
| `mkfs.ext4` asks "Proceed anyway?" | An old `data.ext4` was left over. Answer `y`, or delete it first with `rm data.ext4` |
| `scp` says "No such file" | You're not in `~/beaglebone-image`; run `cd ~/beaglebone-image` |
| Part 3.1 checksums differ | Stop. The eMMC's table isn't the one `mbr-new.bin` was built from (for example, the eMMC holds a different image) |
| After the reboot, no `mmcblk1p3` in `/proc/partitions` | The new table wasn't written. Repeat 3.1 (the eMMC's checksum should now match `md5sum < ~/mbr-new.bin`) and 3.2, then reboot |
| `~/mbr-new.bin: No such file` after the reboot | You copied to `/tmp`, which is emptied at reboot. Copy the files again to the home folder (`root@evb-beaglebone.local:`) |
| 4.2 prints `xzcat: … No such file or directory` (and `0+0 records out`) | Nothing was written. `data.ext4.xz` isn't in the home folder: copy it again (2.5) and repeat 4.2 |
| `mount: mounting /dev/mmcblk1p3 on /data failed: Invalid argument` | Partition 3 has no filesystem yet: 4.2 didn't complete. Repeat 4.2 |
| `/data` isn't mounted after a reboot | Check the last line of `/etc/fstab` (4.4); run `mount /dev/mmcblk1p3 /data` to see the error |
