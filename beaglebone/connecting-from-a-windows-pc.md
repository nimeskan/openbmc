# Connecting to the BeagleBone BMC from a Windows PC

How to reach the BMC's terminal, web UI and Redfish API from a Windows 10 or
Windows 11 PC, including **without any network**: just one cable between the
PC and the board.

There are three ways in:

| Way | Needs | Gives you |
| --- | --- | --- |
| [A. Serial terminal](#a-serial-terminal-no-network-at-all) | 3.3 V USB-serial cable on header J1 | A login shell, and every boot message. No Redfish. |
| [B. Direct Ethernet cable](#b-direct-ethernet-cable-pc--beaglebone-no-router) | One Ethernet cable, PC ↔ BeagleBone | Web UI, Redfish, SSH. No router or internet needed. |
| [C. Your home network](#c-through-your-home-network-router) | Board plugged into your router | Same as B; the router hands out addresses |

Default login everywhere: user **`root`**, password **`0penBmc`** (zero, not the
letter O).

The network facts below were checked in the released image
(`beaglebone-20261004-0244`): its network settings, hostname and enabled
services. The steps haven't been tried on a real board yet.

---

## A. Serial terminal (no network at all)

The BeagleBone's debug serial port (UART0) is on the 6-pin header **J1**. The
image puts a login prompt there, and the bootloader and kernel print their
messages there too, so it shows everything from the moment you apply power.
It's the best tool when something doesn't work.

> The **mini-USB port is not connected to this serial port**. In this image
> it only powers the board. (Stock BeagleBone Debian images add a serial port
> over USB in software; OpenBMC doesn't.)

### What you need

A **3.3 V** USB-to-serial (TTL) cable or adapter: FTDI TTL-232R-3V3, or any
CP2102 / FT232 / CH340 adapter set to 3.3 V. **Not** a 5 V adapter and not an
RS-232 (9-pin) cable: those can damage the board.

### Wiring

| J1 pin | Board signal | Cable wire |
| --- | --- | --- |
| 1 (marked with a dot) | GND | GND (usually black) |
| 4 | RX (board receives) | TX (cable sends) |
| 5 | TX (board sends) | RX (cable receives) |

Leave the cable's VCC/power wire unconnected.

### On Windows

1. Plug the cable into the PC. Windows usually installs the driver itself; if
   not, get it from the chip maker (FTDI, Silicon Labs for CP2102, WCH for CH340).
2. Find its port: right-click **Start → Device Manager → Ports (COM & LPT)**.
   It shows as e.g. **USB Serial Port (COM5)**.
3. Install [PuTTY](https://www.putty.org/) and open it:
   * **Connection type:** Serial
   * **Serial line:** `COM5` (yours)
   * **Speed:** `115200`
   * Under **Connection → Serial**: 8 data bits, 1 stop bit, parity None,
     flow control **None**
   * Click **Open**.
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

Redfish is a web API: it only answers over HTTPS on the network port. The image
has no web client of its own (no `curl`, no browser). Over serial you can
still see the **same data** Redfish is built from, straight from D-Bus. For
example, `busctl tree xyz.openbmc_project.State.BMC` shows what Redfish reports
under `/redfish/v1/Managers/bmc`. For the real Redfish JSON, use B or C.

---

## B. Direct Ethernet cable: PC ↔ BeagleBone, no router

One Ethernet cable from the PC's Ethernet port to the BeagleBone's. A normal
cable is fine: both sides swap the wires automatically, so you don't need a
"crossover" cable.

### How the two find each other

Without a router, nobody hands out IP addresses. Both sides handle that on
their own:

* **The BeagleBone** asks for an address (DHCP). Its network settings
  (`/usr/lib/systemd/network/60-phosphor-networkd-default.network`) also have
  `LinkLocalAddressing=yes`, so it gives itself an automatic address
  **`169.254.x.y`** when nobody answers.
* **Windows** does the same: if no DHCP server answers, it picks its own
  `169.254.x.y` address after about a minute (Windows calls this APIPA).

Addresses in `169.254.0.0/16` can talk to each other directly, so the two
connect with no setup.

### Steps

1. Connect the cable and boot the board. Wait 1–2 minutes.
2. Windows may show **"Unidentified network"** or **"No internet"** for that
   Ethernet connection. That's normal and fine.
3. **Find the board.** Try these in order:
   * **By name (easiest).** The board's hostname is `evb-beaglebone` and it
     runs **avahi**, which announces that name on the local network (mDNS).
     Windows 10/11 can usually look such `.local` names up. In **Command
     Prompt**:
     ```bat
     ping evb-beaglebone.local
     ```
     If you get replies, use `evb-beaglebone.local` as the address below.
   * **From the serial terminal.** Run `ip addr show eth0` and look for
     `inet 169.254.x.y/16`.
4. Open a browser on the PC and go to:
   * `https://evb-beaglebone.local/`, or `https://169.254.x.y/`: the **web UI**
   * `https://…/redfish/v1`: raw **Redfish** JSON
5. The browser warns that the connection isn't private (the BMC made its own
   certificate). In Edge or Chrome click **Advanced → Continue to … (unsafe)**;
   in Firefox **Advanced → Accept the Risk and Continue**. On a cable to your own
   board, that's expected.
6. Log in to the web UI as `root` / `0penBmc`.

You can check the PC's own address in Command Prompt with `ipconfig` (look
under "Ethernet adapter Ethernet" for `Autoconfiguration IPv4 Address . . : 169.254…`).

### Alternative: fixed addresses

If automatic addresses don't work, or you want addresses that are easy to
remember, give both sides one by hand.

**On the board** (serial terminal):

```sh
ip addr add 192.168.50.2/24 dev eth0
```

This is temporary: it's gone after a reboot.

**On the PC** (Windows 11; Windows 10 is very similar):

1. **Start → Settings → Network & internet → Ethernet**.
2. Next to **IP assignment**, click **Edit**, choose **Manual**, switch **IPv4** on.
3. **IP address** `192.168.50.1`, **Subnet mask** `255.255.255.0`
   (Windows 10 asks for "Subnet prefix length": `24`).
   Leave gateway and DNS empty. **Save**.
4. Browse to `https://192.168.50.2/`.

When you're done, set **IP assignment** back to **Automatic (DHCP)**, or your
PC's Ethernet port won't work on normal networks.

---

## C. Through your home network (router)

Plug the BeagleBone into your router. The router gives it an address by DHCP.
Find it with `ping evb-beaglebone.local`, in the router's list of connected
devices, or with `ip addr show eth0` on the serial terminal. Then use the
browser, `curl.exe` and SSH exactly as below.

---

## Using Redfish from Windows

### In the browser

* `https://<board>/`: the web UI, which itself uses Redfish. Sensors are under
  **Hardware status → Sensors**, logs under **Logs**.
* `https://<board>/redfish/v1`: the Redfish service root, readable without
  logging in. Edge and Firefox show JSON in a readable form.

`<board>` means `evb-beaglebone.local`, `169.254.x.y` or `192.168.50.2`,
whichever worked above.

### With curl (built into Windows 10 and 11)

Open **Command Prompt** or **PowerShell**. In PowerShell type **`curl.exe`**,
not `curl`: in Windows PowerShell 5.1, `curl` is a shortcut for a different
command (`Invoke-WebRequest`) that takes different options.

```bat
:: Service root (no login needed)
curl.exe -k https://evb-beaglebone.local/redfish/v1

:: BMC information (user and password with -u)
curl.exe -k -u root:0penBmc https://evb-beaglebone.local/redfish/v1/Managers/bmc

:: List the chassis
curl.exe -k -u root:0penBmc https://evb-beaglebone.local/redfish/v1/Chassis
```

`-k` accepts the BMC's self-made certificate. `-u root:0penBmc` logs in.

### Readable output in PowerShell

PowerShell can turn the JSON into a table-like view (`Out-String` first joins
curl's output lines into one text, which `ConvertFrom-Json` needs):

```powershell
curl.exe -sk -u root:0penBmc https://evb-beaglebone.local/redfish/v1/Managers/bmc |
    Out-String | ConvertFrom-Json | Select-Object Name, FirmwareVersion, PowerState
```

Or print it neatly indented:

```powershell
curl.exe -sk -u root:0penBmc https://evb-beaglebone.local/redfish/v1/Managers/bmc |
    Out-String | ConvertFrom-Json | ConvertTo-Json -Depth 6
```

### Change the default password

```bat
curl.exe -k -u root:0penBmc -X PATCH -H "Content-Type: application/json" ^
  https://evb-beaglebone.local/redfish/v1/AccountService/Accounts/root ^
  -d "{\"Password\": \"a-new-strong-password\"}"
```

(In Command Prompt, `^` continues a command on the next line, and the `"`
inside the JSON have to be written as `\"`.)

### More

The [Redfish and I2C sensor guide](redfish-i2c-sensor/README.md) explains what
Redfish is, which URLs exist, and how sensors appear there. Its examples are
written for a Linux/macOS terminal; on Windows, use `curl.exe` as shown here.

---

## SSH from Windows

Windows 10 and 11 include an SSH client. In Command Prompt or PowerShell:

```bat
ssh root@evb-beaglebone.local
```

Answer `yes` to the first-connection question, then enter `0penBmc`. You get
the same shell as on the serial terminal, over the network.

---

## Troubleshooting

| Problem | What to try |
| --- | --- |
| PuTTY shows nothing | Right COM port? TX/RX swapped? Speed 115200, flow control None? GND connected? |
| PuTTY shows garbage characters | Wrong speed: must be 115200 |
| `ping evb-beaglebone.local` fails | Use the address from `ip addr show eth0` (serial terminal) instead. Wait 1–2 minutes after boot. |
| PC has no `169.254…` address in `ipconfig` | Wait a minute; or unplug and replug the cable; or use fixed addresses |
| Browser "can't reach this page" | `ping` the board's address first. If ping works but the browser doesn't, make sure you typed `https://`, not `http://` |
| `curl` complains about unknown options in PowerShell | Type `curl.exe`, not `curl` |
| `401 Unauthorized` | Wrong user or password (`root` / `0penBmc` unless you changed it) |
| Board not on the network at all | Check on the serial terminal: `ip addr show eth0` should show `state UP`; `systemctl status systemd-networkd` |
