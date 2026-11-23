# Connecting over USB (CDC-NCM network gadget)

This guide turns the BeagleBone's **mini-USB port** into a **USB network
adapter**. With one USB cable between the board and a PC, you get:
* SSH;
* the web UI;
* Redfish.

There's no Ethernet cable, no router, and no network settings to change on
the PC: the board hands the PC an address itself. It works **alongside** the
Ethernet connection you already have, not instead of it.

```
                  eth0  10.42.0.x    ── Ethernet cable ──  Ubuntu PC ("Shared" profile)   (unchanged)
   BeagleBone
                  usb0  192.168.7.2  ── mini-USB cable ──  any Linux or Windows PC
                                                          (gets 192.168.7.100-119 from the board)
```

**CDC-NCM** ("Communications Device Class, Network Control Model") is the
standard USB class for network adapters. The board's kernel acts as the USB
**device**: Linux calls this a "USB gadget". The PC acts as the USB **host**.

> **What was tested, and how.**
> * **Our image has what's needed.** I checked the files in our released image:
>   * the `g_ncm` gadget module and its helpers are present;
>   * the mini-USB port (USB0) is set to device mode in the device tree;
>   * systemd-networkd has its DHCP server built in, with every setting used
>     in [`50-usb0.network`](usb-ncm/50-usb0.network);
>   * dropbear (SSH), bmcweb (web UI) and avahi listen on all interfaces.
> * **The module settings.** The board's own `modprobe`, run in an ARM
>   emulator, read [`g_ncm.conf`](usb-ncm/g_ncm.conf), applied its options
>   and worked out the module order: `configfs`, `libcomposite`, `u_ether`,
>   `g_ncm`.
> * **The service file** passed `systemd-analyze verify`.
> * **Found while checking:** our image has **no automatic module loading at
>   boot** (systemd's `modules-load` isn't included). So this guide loads the
>   module with a small service of its own.
> * **Not yet:** running it on the board, and connecting real Linux and
>   Windows PCs. Each step says what you should see.

---

## Contents

1. [How it works](#1-how-it-works)
2. [The files](#2-the-files)
3. [Set up the board](#3-set-up-the-board)
4. [Connect from Linux (Ubuntu)](#4-connect-from-linux-ubuntu)
5. [Connect from Windows](#5-connect-from-windows)
6. [Checks and troubleshooting](#6-checks-and-troubleshooting)
7. [Remove it](#7-remove-it)
8. [Later: with the rebuilt image](#8-later-with-the-rebuilt-image)

---

## 1. How it works

```
 BeagleBone                                                      PC
 ┌──────────────────────────────────────────────┐              ┌──────────────────────────────┐
 │ usb-ncm-gadget.service                       │              │                              │
 │   modprobe g_ncm  (+ options from            │              │ Linux: cdc_ncm driver        │
 │   /etc/modprobe.d/g_ncm.conf)                │  USB cable   │ Windows: UsbNcm driver       │
 │      │                                       │◄────────────►│   → new network adapter      │
 │      ▼                                       │              │   → asks for an address      │
 │ USB controller (musb) in device mode         │              │     (DHCP)                   │
 │      │ creates network interface "usb0"      │              │                              │
 │      ▼                                       │              │ gets 192.168.7.100-119,      │
 │ systemd-networkd + 50-usb0.network:          │              │ no gateway, no DNS           │
 │   usb0 = 192.168.7.2/24, DHCP server on      │              │                              │
 │      │                                       │              │ ssh root@192.168.7.2         │
 │      ▼                                       │              │ https://192.168.7.2/         │
 │ SSH (dropbear), web UI (bmcweb), avahi:      │              │                              │
 │   already listen on every interface          │              │                              │
 └──────────────────────────────────────────────┘              └──────────────────────────────┘
```

* **`g_ncm`** is a ready-made kernel module that sets the USB port up as an
  NCM network adapter. Loading it creates a network interface called
  **`usb0`** on the board.
* **systemd-networkd** (the board's network manager) configures `usb0` from
  our settings file: a **fixed address** `192.168.7.2`, and a small **DHCP
  server** that hands the PC an address.
* **Nothing else needs changing.** SSH, the web UI and avahi
  (`evb-beaglebone.local`) already listen on every network interface.

### Why your Ethernet connection isn't affected

* **Separate interfaces, separate subnets.** `eth0` stays on `10.42.0.x`
  from your Ubuntu PC's "Shared" connection. `usb0` is on `192.168.7.x`.
  Linux sends traffic for each subnet out of the matching interface.
* **Our settings file matches only `usb0`, by name** (`[Match] Name=usb0`).
  OpenBMC's default file (`60-phosphor-networkd-default.network`) matches
  *every* Ethernet-type interface (`Type=ether`), and keeps doing that for
  `eth0`. Our file's `50-` prefix only makes it win **for `usb0`**.
* **The board's default route stays on `eth0`.** `usb0` gets a fixed address
  with no gateway.
* **The board doesn't offer itself as the PC's router or DNS server**
  (`EmitRouter=no`, `EmitDNS=no`). The PC therefore keeps using its own
  network for the internet, and `192.168.7.x` is a private link to the board
  only.

---

## 2. The files

All in [`usb-ncm/`](usb-ncm/):

| File | Goes to (on the board) | What it does |
| --- | --- | --- |
| [`g_ncm.conf`](usb-ncm/g_ncm.conf) | `/etc/modprobe.d/g_ncm.conf` | Options `modprobe` applies whenever `g_ncm` is loaded: fixed MAC addresses and a product name |
| [`usb-ncm-gadget.service`](usb-ncm/usb-ncm-gadget.service) | `/etc/systemd/system/usb-ncm-gadget.service` | Loads `g_ncm` at every boot (and unloads it when stopped) |
| [`50-usb0.network`](usb-ncm/50-usb0.network) | `/etc/systemd/network/50-usb0.network` | Address and DHCP server for `usb0` |

All three are in `/etc`, so they survive reboots but are **wiped by
re-flashing** the eMMC.

### `g_ncm.conf`

```
options g_ncm dev_addr=02:bb:00:00:00:02 host_addr=02:bb:00:00:00:01 iProduct=BeagleBone-OpenBMC-USB-network
```

| Part | Meaning |
| --- | --- |
| `options g_ncm …` | Whenever `g_ncm` is loaded, pass it these parameters |
| `dev_addr=02:bb:00:00:00:02` | MAC address of the **board's** side (`usb0`) |
| `host_addr=02:bb:00:00:00:01` | MAC address of the **PC's** side |
| `iProduct=…` | The product name the PC shows for the device |

**Why fixed MAC addresses?** Without them, `g_ncm` picks **random** ones at
every load. The PC would then see a "new" network adapter after every board
reboot: Ubuntu would create yet another connection, and Windows yet another
"Network 2, 3, 4…". Addresses starting with `02` are **locally administered**:
they're reserved for exactly this, and never clash with real hardware. If you
ever connect **two** BeagleBones to one PC, give each its own pair (e.g.
`…:00:12` and `…:00:11`).

These parameters come from the module itself. `g_ncm`'s built-in description
(`.modinfo`) lists `host_addr`, `dev_addr`, `qmult`, `iProduct`,
`iManufacturer`, `iSerialNumber`, `bcdDevice`, `idProduct` and `idVendor`.

### `usb-ncm-gadget.service`

```ini
[Unit]
Description=USB network gadget (CDC-NCM) on the mini-USB port

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/modprobe g_ncm
ExecStop=/sbin/modprobe -r g_ncm

[Install]
WantedBy=multi-user.target
```

| Line | Meaning |
| --- | --- |
| `Type=oneshot` | The service runs one command and is done (it isn't a program that keeps running) |
| `RemainAfterExit=yes` | …but counts as "active" afterwards, so `systemctl stop` can run `ExecStop` |
| `ExecStart=/sbin/modprobe g_ncm` | Load the module, plus the modules it depends on, with our options |
| `ExecStop=/sbin/modprobe -r g_ncm` | Unload it: `usb0` disappears and the PC sees the adapter unplugged |
| `WantedBy=multi-user.target` | `systemctl enable` makes it run at every boot |

**Why a service, and not `/etc/modules-load.d/`?** On most Linux systems,
listing a module name in `/etc/modules-load.d/*.conf` loads it at boot.
That's done by systemd's `systemd-modules-load` program, which **isn't
included in our image**. So a file there would be silently ignored.

### `50-usb0.network`

```ini
[Match]
Name=usb0                     # only the USB interface

[Link]
RequiredForOnline=no          # don't hold up the boot waiting for USB (cable may be unplugged)

[Network]
Address=192.168.7.2/24        # the board's fixed address; /24 = the subnet 192.168.7.0-255
DHCPServer=yes                # hand out addresses on this link
LinkLocalAddressing=ipv6      # no 169.254.x.x IPv4 address here; keep IPv6 link-local
IPv6AcceptRA=no               # don't take IPv6 router announcements from the PC

[DHCPServer]
PoolOffset=100                # hand out addresses starting at 192.168.7.100 ...
PoolSize=20                   # ... 20 of them (up to .119)
EmitRouter=no                 # don't tell the PC to use the board as its router
EmitDNS=no                    # ... or as its DNS server
EmitNTP=no                    # ... or as its time server
```

(The real file has these explanations on separate comment lines.
systemd-networkd doesn't allow a comment at the end of a setting line.)

* **The `50-` prefix.** systemd-networkd uses the **first** file, in name
  order, whose `[Match]` fits an interface. `50-usb0.network` comes before
  OpenBMC's `60-phosphor-networkd-default.network`, so it wins for `usb0`;
  `eth0` doesn't match it and still gets the `60-` file.
* **`192.168.7.x`** is the range BeagleBoard.org's own images use for USB
  networking. If a PC's own network already uses `192.168.7.x`, change both
  `Address=` here and the addresses in the rest of this guide to another
  private range, e.g. `192.168.77.2/24`.

---

## 3. Set up the board

Do this over your **existing** connection: SSH over Ethernet, or the serial
console.

### 3a. Copy the files to the board (on the PC)

```sh
mkdir -p ~/bbb-usb-ncm && cd ~/bbb-usb-ncm
BASE=https://raw.githubusercontent.com/nimeskan/openbmc/main/beaglebone/usb-ncm
wget $BASE/g_ncm.conf $BASE/usb-ncm-gadget.service $BASE/50-usb0.network
scp g_ncm.conf usb-ncm-gadget.service 50-usb0.network root@evb-beaglebone.local:
```

### 3b. Install them (on the board)

```sh
mkdir -p /etc/modprobe.d
install -m 0644 ~/g_ncm.conf /etc/modprobe.d/g_ncm.conf
install -m 0644 ~/50-usb0.network /etc/systemd/network/50-usb0.network
install -m 0644 ~/usb-ncm-gadget.service /etc/systemd/system/usb-ncm-gadget.service
```

`install -m 0644 <from> <to>` copies a file and sets its permissions: owner
can read and write, everyone else can read.

### 3c. Make systemd and the network manager read them

```sh
systemctl daemon-reload
networkctl reload
```

| Command | Meaning |
| --- | --- |
| `systemctl daemon-reload` | systemd re-reads its unit files, so it sees the new service |
| `networkctl reload` | systemd-networkd re-reads its `.network` files. Existing interfaces like `eth0` keep working. |

### 3d. Start it now, and at every boot

```sh
systemctl enable --now usb-ncm-gadget.service
```

`enable` makes it start at every boot; `--now` also starts it right away.

### 3e. Check the board side

```sh
dmesg | tail -5
ip addr show usb0
networkctl status usb0
ip addr show eth0
```

| Command | Expected |
| --- | --- |
| `dmesg \| tail -5` | Kernel messages about the gadget, e.g. lines mentioning `g_ncm`, `NCM Gadget` and `usb0` with MAC `02:bb:00:00:00:02` |
| `ip addr show usb0` | `link/ether 02:bb:00:00:00:02` and `inet 192.168.7.2/24`. With no USB cable plugged into a PC, the state shows `NO-CARRIER`/`DOWN`. That's normal: the address and DHCP server become active when a PC is connected. |
| `networkctl status usb0` | `Network File: /etc/systemd/network/50-usb0.network`. Once a PC is connected, the state is `routable` or `configured`, and its DHCP section lists the address handed to the PC. |
| `ip addr show eth0` | **Unchanged**: still your `10.42.0.x` address. This confirms the Ethernet connection isn't affected. |

---

## 4. Connect from Linux (Ubuntu)

Ubuntu's kernel has the `cdc_ncm` driver built in, and NetworkManager sets the
new adapter up automatically. Nothing to install.

**1. Plug** a USB cable from the BeagleBone's **mini-USB** port into the PC.

* That cable can also **power** the board. If the board is already powered
  from the barrel jack, that's fine: keep both.
* If the mini-USB cable is its **only** power, the board starts booting when
  you plug it in. Give it about a minute.

**2. See the new adapter:**

```sh
ip -br addr
```

* `-br` ("brief") prints one line per interface: name, state, addresses.
* Expected: a new interface named **`enx02bb00000001`**. Ubuntu names USB
  network adapters `enx` plus their MAC address, which here is
  `host_addr=02:bb:00:00:00:01` from `g_ncm.conf`.
* After a few seconds, that interface shows `UP` and an address
  **`192.168.7.1xx/24`** from the board.

To see what NetworkManager did:

```sh
nmcli device status
```

The new device shows `connected` to an automatic profile, usually
`Wired connection 2`. It's separate from your `beaglebone` profile, which is
tied to the Ethernet port `enp0s31f6`, so both work at once.

**3. Connect:**

```sh
ping -c 3 192.168.7.2
ssh root@192.168.7.2
```

* **Web UI:** `https://192.168.7.2/` in a browser. Accept the certificate
  warning, as over Ethernet.
* **Redfish:**
  ```sh
  curl -k -u root https://192.168.7.2/redfish/v1/Systems/system
  ```
* `ssh root@evb-beaglebone.local` may also work over USB, but if both cables
  are connected, the name can resolve to either address. Both reach the same
  board.

**First SSH over USB:** SSH asks you to confirm the board's identity once
(`Are you sure you want to continue connecting (yes/no)?`) for the new address
`192.168.7.2`. Type `yes`. It's the same board and key, just a new address
for SSH to remember.

### If Ubuntu doesn't get an address

```sh
nmcli device connect enx02bb00000001
```

This tells NetworkManager to bring that adapter up with its automatic
settings (DHCP). Check the interface name with `ip -br link` first.

If the PC uses a different network manager, or you want a fixed address
instead:

```sh
sudo ip addr add 192.168.7.50/24 dev enx02bb00000001
sudo ip link set enx02bb00000001 up
```

This gives the PC a fixed address in the same subnet, until the cable is
unplugged.

---

## 5. Connect from Windows

**1. Plug** the BeagleBone's mini-USB port into the PC, and give the board
a minute if this cable powers it.

**2. Check that Windows installed the network adapter.** Press **Win+X** →
**Device Manager**:

* **Expected:** under **Network adapters**, a new entry such as **"UsbNcm Host
  Device"**. Then go to step 3.
* **If there's instead an unknown device** (yellow warning triangle) under
  **Other devices**, e.g. "CDC NCM" or "BeagleBone-OpenBMC-USB-network",
  Windows didn't pick its driver automatically. Do the one-time manual step
  below.

**Why this can happen.** Windows (10 and 11) includes a CDC-NCM driver,
`UsbNcm.sys`. But it doesn't always attach it to an NCM device on its own.
Windows looks for an extra "Microsoft OS descriptor" in the device that says
"use the NCM driver". The ready-made `g_ncm` module we're using doesn't send
one. (The newer configfs gadget method can; see
[section 8](#8-later-with-the-rebuilt-image).)

**Manual driver selection (once per PC):**
1. Right-click the unknown device → **Update driver**.
2. **Browse my computer for drivers**.
3. **Let me pick from a list of available drivers on my computer**.
4. Choose **Network adapters** → **Next**.
5. Manufacturer: **Microsoft** → Model: **UsbNcm Host Device** → **Next**.
   Accept the warning, if any.
6. The device moves to **Network adapters**.

Windows remembers this for this device (and its fixed MAC address), so it's
needed only once.

I can't check the exact names in the Windows dialogs from here; they may
differ slightly between Windows versions. If the "UsbNcm Host Device" model
isn't listed, that Windows version doesn't include the NCM driver. Use the
Ethernet method from
[`connecting-from-a-windows-pc.md`](connecting-from-a-windows-pc.md), or wait
for the rebuilt image ([section 8](#8-later-with-the-rebuilt-image)).

**3. Check the address.** Open **PowerShell** or **Command Prompt** and run:

```
ipconfig
```

* Expected: an adapter (named something like "Ethernet 3") with
  **IPv4 Address `192.168.7.1xx`**, subnet mask `255.255.255.0`, and **no**
  default gateway.
* No default gateway is deliberate: Windows keeps using its normal network
  for the internet.
* Windows may ask whether this "network" is public or private, or show it as
  "Unidentified network". Either is fine: connecting **out** to the board
  works on both. (Choose "Public" if asked.)

**4. Connect:**

```
ping 192.168.7.2
ssh root@192.168.7.2
```

* Windows 10 and 11 include an SSH client (`ssh`). If it's missing: Settings
  → Apps → Optional features → add **OpenSSH Client**. PuTTY also works: host
  `192.168.7.2`, port 22.
* **Web UI:** `https://192.168.7.2/` in a browser.
* **Redfish:**
  ```
  curl.exe -k -u root https://192.168.7.2/redfish/v1/Systems/system
  ```
  Use `curl.exe`, not `curl`, in PowerShell: there `curl` is an alias for a
  different command.

`evb-beaglebone.local` often works on Windows 10/11 too, but the fixed
address `192.168.7.2` is the reliable choice.

---

## 6. Checks and troubleshooting

**On the board:**

```sh
systemctl status usb-ncm-gadget.service
cat /sys/class/udc/*/state
journalctl -u systemd-networkd -b --no-pager | grep usb0
```

| Command | What it tells you |
| --- | --- |
| `systemctl status usb-ncm-gadget.service` | `active (exited)` = the module was loaded successfully. ("exited" is normal for a one-shot service.) |
| `cat /sys/class/udc/*/state` | The USB **device controller** ("UDC")'s state: `configured` = a PC is connected and has set the device up; `not attached` = no PC on the cable |
| `journalctl -u systemd-networkd -b … \| grep usb0` | The network manager's messages about `usb0`: link up or down, DHCP leases given |

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `modprobe: FATAL: Module g_ncm not found` | Running on a different image | This needs our OpenBMC image (it has `g_ncm`). Check `ls /lib/modules/$(uname -r)/kernel/drivers/usb/gadget/legacy/`. |
| `modprobe: ERROR: could not insert 'g_ncm': Device or resource busy` | Another gadget already uses the port (e.g. `g_mass_storage` loaded by hand) | `lsmod \| grep g_`, then `modprobe -r` the other one |
| `usb0` doesn't exist | Module not loaded | `systemctl status usb-ncm-gadget.service`; `dmesg \| tail` |
| `usb0` has no `192.168.7.2` | `.network` file not read, or a typo in it | `networkctl status usb0` must show `Network File: /etc/systemd/network/50-usb0.network`. Then `networkctl reload`. |
| UDC state `not attached` with a cable plugged in | Charge-only cable (no data wires), or the cable is in the board's **USB-A** host socket | Use a known **data** cable in the **mini-USB** socket |
| PC gets a `169.254.x.x` address | The PC didn't get an answer from the board's DHCP server | On the board: `networkctl status usb0` and the `journalctl` line above. On the PC: unplug and replug. As a fallback, give the PC a fixed address (section 4). |
| PC lost **internet** after plugging in | It's using the board as a gateway | Check `EmitRouter=no` is in `50-usb0.network`; `networkctl reload`; unplug and replug |
| `eth0` lost its address | `50-usb0.network` edited to match more than `usb0` | It must say `Name=usb0` under `[Match]` |
| Windows: unknown device, yellow triangle | NCM driver not picked automatically | Section 5, manual driver selection |
| Windows: a new "Network 2, 3…" each time | MAC addresses not fixed | Check `/etc/modprobe.d/g_ncm.conf`; `cat /sys/class/net/usb0/address` must be `02:bb:00:00:00:02` |
| The web UI shows a second network interface (`usb0`) | Expected: OpenBMC lists every interface | Don't change `usb0`'s settings there. That would make OpenBMC write its own file for `usb0`, which overrides ours. |

---

## 7. Remove it

On the board:

```sh
systemctl disable --now usb-ncm-gadget.service
rm /etc/systemd/system/usb-ncm-gadget.service
rm /etc/systemd/network/50-usb0.network
rm /etc/modprobe.d/g_ncm.conf
systemctl daemon-reload
networkctl reload
rm ~/g_ncm.conf ~/usb-ncm-gadget.service ~/50-usb0.network   # optional: the copies
```

* `disable --now` unloads `g_ncm` (`ExecStop`): `usb0` disappears and the PC
  sees the adapter unplugged.
* After `rm` and the reloads, nothing loads it again at boot.
* `ip addr show eth0` still shows your Ethernet address.
* On the PC you can delete the leftover connection if you like: Ubuntu
  `nmcli connection delete "Wired connection 2"`; Windows forgets the
  adapter by itself once it's gone.

---

## 8. Later: with the rebuilt image

The planned toolbox rebuild adds the kernel options `CONFIG_USB_CONFIGFS`,
`CONFIG_USB_CONFIGFS_NCM` and `CONFIG_USB_CONFIGFS_ACM`. With these, the USB
device is built from parts at run time, by writing files under
`/sys/kernel/config/usb_gadget/`, instead of loading the fixed `g_ncm` module.
That allows:

* **Network and serial on one cable:** NCM plus a CDC-ACM serial port
  (`/dev/ttyGS0` on the board; `/dev/ttyACM0` on Linux; a COM port on
  Windows). The serial port can run a login console.
* **Automatic driver selection on Windows:** the gadget can include the
  "Microsoft OS descriptor" naming the NCM driver (`WINNCM`). The kernel's NCM
  function supports this, and Windows should then pick `UsbNcm` without the
  manual step. That's to be confirmed when we get there.

Everything else in this guide (the `usb0` network file, the PC side) stays
the same.
