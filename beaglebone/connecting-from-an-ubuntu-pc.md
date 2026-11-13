# Connecting to the BeagleBone BMC from an Ubuntu PC

How to reach the BMC's terminal, web UI and Redfish API from an Ubuntu PC,
including **without any network**: just one Ethernet cable between the PC and
the board. (On Windows? See
[connecting-from-a-windows-pc.md](connecting-from-a-windows-pc.md).)

Haven't written the image to a card yet? See
[flashing-the-sd-card-on-ubuntu.md](flashing-the-sd-card-on-ubuntu.md).

Written for **Ubuntu Desktop 22.04 / 24.04**, which uses NetworkManager for
network settings. Ubuntu Server is covered briefly at the end.

There are three ways in:

| Way | Needs | Gives you |
| --- | --- | --- |
| [A. Serial terminal](#a-serial-terminal-no-network-at-all) | 3.3 V USB-serial cable on header J1 | A login shell, and every boot message. No Redfish. |
| [B. Direct Ethernet cable](#b-direct-ethernet-cable-ubuntu--beaglebone-no-router) | One Ethernet cable, PC ↔ BeagleBone | Web UI, Redfish, SSH. No router or internet needed. |
| [C. Your home network](#c-through-your-home-network-router) | Board plugged into your router | Same as B; the router hands out addresses |

Default login everywhere: user **`root`**, password **`0penBmc`** (zero, not the
letter O).

The board-side facts were checked in the released image
(`beaglebone-20261004-0244`): the board asks for an address by DHCP, falls back
to an automatic `169.254.x.y` address, is named `evb-beaglebone`, and announces
that name with avahi. The NetworkManager settings below were checked against
NetworkManager's own manual (version 1.46, the one in Ubuntu 24.04). None of
the steps have been tried on a real board yet.

---

## A. Serial terminal (no network at all)

The BeagleBone's debug serial port (UART0) is on the 6-pin header **J1**. The
image puts a login prompt there, and the bootloader and kernel print their
messages there too, so it shows everything from the moment you apply power.
It's the best tool when something doesn't work.

> The **mini-USB port is not connected to this serial port**. In this image
> it only powers the board.

### What you need, and the wiring

A **3.3 V** USB-to-serial (TTL) cable or adapter (FTDI TTL-232R-3V3, or any
CP2102 / FT232 / CH340 adapter set to 3.3 V). **Not** a 5 V adapter and not an
RS-232 (9-pin) cable: those can damage the board.

| J1 pin | Board signal | Cable wire |
| --- | --- | --- |
| 1 (marked with a dot) | GND | GND (usually black) |
| 4 | RX (board receives) | TX (cable sends) |
| 5 | TX (board sends) | RX (cable receives) |

Leave the cable's VCC/power wire unconnected.

### On Ubuntu

1. **Allow your user to open serial ports.** Serial devices belong to the
   `dialout` group. Run this once, then **log out and back in** (or reboot):
   ```sh
   sudo usermod -aG dialout $USER
   ```
2. Plug in the cable and find its device name:
   ```sh
   sudo dmesg | tail
   ls /dev/ttyUSB*
   ```
   You should see something like `/dev/ttyUSB0`. (Some adapters show up as
   `/dev/ttyACM0`.)
3. Install a terminal program and open the port at 115200 baud:
   ```sh
   sudo apt install picocom
   picocom -b 115200 /dev/ttyUSB0
   ```
   To quit picocom, press **Ctrl+A, then Ctrl+X**. Alternatives:
   `screen /dev/ttyUSB0 115200` (quit with Ctrl+A, then `\`) or `minicom`.
4. Power on the board (hold **S2** to boot from the SD card). You'll see
   `U-Boot SPL …`, then `U-Boot …`, then Linux boot messages, then:
   ```
   evb-beaglebone login:
   ```
   If the screen stays quiet once it's booted, press Enter.
5. Log in as `root` / `0penBmc`.

### Useful commands on the board

```sh
ip addr show eth0           # the board's network address(es)
systemctl --failed          # services that didn't start
journalctl -b               # everything logged since boot
busctl tree | head -40      # what OpenBMC has published on D-Bus
```

### Why you can't see Redfish here

Redfish is a web API: it only answers over HTTPS on the network port, and the
image has no web client of its own (no `curl`, no browser). Over serial you can
see the same data Redfish is built from, straight from D-Bus. For the real
Redfish JSON, use B or C.

---

## B. Direct Ethernet cable: Ubuntu ↔ BeagleBone, no router

One Ethernet cable from the PC's Ethernet port to the BeagleBone's. A normal
cable is fine: both sides swap the wires automatically.

### The one thing that's different from Windows

With no router, nobody hands out addresses. **Windows then gives itself an
automatic `169.254.x.y` address, but Ubuntu does not**: with its default
setting ("Automatic (DHCP)"), NetworkManager waits for a DHCP server, gives up,
and leaves the Ethernet port without an address. So you have to tell Ubuntu how
the cable should work. There are three ways. Pick one:

| Method | What happens | Best for |
| --- | --- | --- |
| **1. Shared to other computers** (recommended) | Ubuntu becomes the DHCP server (it gives itself `10.42.0.1` and hands the board an address like `10.42.0.x`) | Easiest. Nothing to type on the board |
| **2. Link-Local Only** | Both sides pick random `169.254.x.y` addresses | Also needs nothing on the board |
| **3. Manual (fixed addresses)** | You choose both addresses | Predictable addresses; needs a command on the board |

All of this changes how the PC's **wired network port** is configured. To keep
your normal wired settings untouched, the commands below create a **separate
profile** named `beaglebone`, which only turns on when you ask for it.

### Step 1: Find the Ethernet port's name

```sh
nmcli device status
```

Look for the row with TYPE `ethernet`, for example `enp3s0` (modern Ubuntu
doesn't call it `eth0`). Below, replace `enp3s0` with yours.

### Step 2: Create the profile (pick ONE method)

**Method 1: Shared to other computers** (recommended)

```sh
nmcli connection add type ethernet ifname enp3s0 con-name beaglebone \
    connection.autoconnect no ipv4.method shared
```

**Method 2: Link-Local Only**

```sh
nmcli connection add type ethernet ifname enp3s0 con-name beaglebone \
    connection.autoconnect no ipv4.method link-local ipv6.method ignore
```

**Method 3: Manual**

```sh
nmcli connection add type ethernet ifname enp3s0 con-name beaglebone \
    connection.autoconnect no ipv4.method manual ipv4.addresses 192.168.50.1/24 \
    ipv6.method ignore
```

(For method 3, also run `ip addr add 192.168.50.2/24 dev eth0` on the board's
serial terminal after it boots; the address is gone after a reboot.)

*Prefer the graphical way?* **Settings → Network**, click the **gear** next to
**Wired**, open the **IPv4** tab, and choose **Shared to other computers**,
**Link-Local Only** or **Manual**. This changes your existing wired profile
instead of making a separate one, so remember to switch it back to
**Automatic (DHCP)** afterwards.

### Step 3: Connect the cable, boot the board, turn the profile on

1. Plug in the cable and boot the board. Wait 1–2 minutes.
2. Activate the profile:
   ```sh
   nmcli connection up beaglebone
   ```
3. Check that the PC has an address:
   ```sh
   ip -4 addr show enp3s0
   ```
   Method 1 should show `10.42.0.1/24`, method 2 a `169.254.…` address,
   method 3 `192.168.50.1/24`.

### Step 4: Find the board

Try these in order:

* **By name (easiest).** The board's hostname is `evb-beaglebone` and it
  announces that name with avahi (mDNS). Ubuntu Desktop resolves `.local` names
  out of the box:
  ```sh
  ping -c 3 evb-beaglebone.local
  ```
  If you get replies, use `evb-beaglebone.local` as the address below. (If
  `ping` says "Name or service not known", install the lookup pieces and try
  again: `sudo apt install avahi-daemon libnss-mdns`.)
* **Ask the PC who's on the cable.** After the ping above (or any traffic),
  ```sh
  ip neigh show dev enp3s0
  ```
  lists the other device's address, for example `10.42.0.38`.
* **From the serial terminal.** Run `ip addr show eth0` on the board and look
  for the `inet` line.

### Step 5: Use it

* In **Firefox** (or any browser), go to `https://evb-beaglebone.local/`, or
  `https://<the address>/`, for the **web UI**, and `https://…/redfish/v1` for
  raw **Redfish** JSON.
* The browser warns that the connection isn't private: the BMC made its own
  certificate. In Firefox click **Advanced → Accept the Risk and Continue**; in
  Chromium-based browsers **Advanced → Proceed to … (unsafe)**. On a cable to
  your own board that's expected.
* Log in to the web UI as `root` / `0penBmc`.

### Step 6: Switch back when you're done

```sh
nmcli connection down beaglebone
```

NetworkManager returns the port to your normal wired profile the next time
you connect to a normal network. If you won't use the setup again, remove it:

```sh
nmcli connection delete beaglebone
```

---

## C. Through your home network (router)

Plug the BeagleBone into your router. The router gives it an address by DHCP,
and your PC uses its normal wired or Wi-Fi connection: no profile needed. Find
the board with `ping evb-beaglebone.local`, in the router's list of connected
devices, or with `ip addr show eth0` on the serial terminal.

---

## Using Redfish from Ubuntu

`<board>` below means `evb-beaglebone.local` or the address you found.

### Command-line tools

```sh
sudo apt install curl jq
```

`-k` accepts the BMC's self-made certificate; `-u root:0penBmc` logs in.

```sh
# Service root (no login needed)
curl -k https://evb-beaglebone.local/redfish/v1

# BMC information, pretty-printed
curl -sk -u root:0penBmc https://evb-beaglebone.local/redfish/v1/Managers/bmc | jq

# Just a few fields
curl -sk -u root:0penBmc https://evb-beaglebone.local/redfish/v1/Managers/bmc \
  | jq '{Name, FirmwareVersion, PowerState}'

# The chassis list
curl -sk -u root:0penBmc https://evb-beaglebone.local/redfish/v1/Chassis | jq
```

### Change the default password

```sh
curl -k -u root:0penBmc -X PATCH -H "Content-Type: application/json" \
  https://evb-beaglebone.local/redfish/v1/AccountService/Accounts/root \
  -d '{"Password": "a-new-strong-password"}'
```

### Watch sensors live

The monitor script in the sensor guide runs on Ubuntu as it is (it needs
`curl` and `jq`, installed above):

```sh
./beaglebone/redfish-i2c-sensor/files/tools/watch-sensors.sh evb-beaglebone.local
```

### More

The [Redfish and I2C sensor guide](redfish-i2c-sensor/README.md) explains what
Redfish is, which URLs exist, and how sensors appear there; its examples are
written for a Linux terminal like yours.

---

## SSH from Ubuntu

```sh
ssh root@evb-beaglebone.local
```

Answer `yes` to the first-connection question, then enter `0penBmc`. You get
the same shell as on the serial terminal, over the network.

If you **re-flash the SD card**, the board makes a new SSH identity and SSH
refuses to connect with "REMOTE HOST IDENTIFICATION HAS CHANGED". That's
expected after a re-flash: forget the old one and connect again:

```sh
ssh-keygen -R evb-beaglebone.local
```

---

## Ubuntu Server (no NetworkManager)

Ubuntu Server doesn't use NetworkManager, so the `nmcli` steps above don't
apply. The quickest way is to give the Ethernet port a temporary fixed address
(gone after a reboot):

```sh
sudo ip link set enp3s0 up
sudo ip addr add 192.168.50.1/24 dev enp3s0
```

Then on the board's serial terminal:

```sh
ip addr add 192.168.50.2/24 dev eth0
```

and use `192.168.50.2` as the address (`ping 192.168.50.2`,
`https://192.168.50.2/`, `ssh root@192.168.50.2`). Remove yours afterwards with
`sudo ip addr del 192.168.50.1/24 dev enp3s0`. (This also works on Ubuntu
Desktop for a quick test, though NetworkManager may undo it.)

---

## Troubleshooting

| Problem | What to try |
| --- | --- |
| `picocom` says "Permission denied" on `/dev/ttyUSB0` | You're not in the `dialout` group yet: run the `usermod` command, then **log out and back in** |
| No `/dev/ttyUSB0` appears | `sudo dmesg \| tail` right after plugging in. On Ubuntu 22.04 and later, a package called `brltty` (for braille displays) can grab some USB-serial adapters. If dmesg mentions `brltty`, run `sudo apt remove brltty`, then unplug and replug |
| picocom shows nothing | Right device? TX/RX swapped? GND connected? Speed must be 115200 |
| picocom shows garbage | Wrong speed: must be 115200 |
| `nmcli connection up beaglebone` fails with "device not available" or "no carrier" | The cable isn't connected or the board isn't powered. Check the link lights |
| `nmcli device status` shows the port as `unmanaged` | Another tool (netplan/systemd-networkd) manages it. See the Ubuntu Server section |
| `ping evb-beaglebone.local` fails | Use `ip neigh show dev enp3s0` or `ip addr show eth0` (serial) to get the address and use that instead. Wait 1–2 minutes after boot. Check `sudo apt install avahi-daemon libnss-mdns` |
| Browser "can't connect" | `ping` the address first. If ping works but the browser doesn't, make sure you typed `https://`, not `http://` |
| `curl: (60) SSL certificate problem` | Add `-k` (the BMC's certificate is self-made) |
| `401 Unauthorized` | Wrong user or password (`root` / `0penBmc` unless you changed it) |
| The PC's wired network doesn't work normally afterwards | `nmcli connection down beaglebone` (or delete the profile); then reconnect your normal wired profile from the network menu |
