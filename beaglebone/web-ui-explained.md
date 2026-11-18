# The OpenBMC web UI, page by page

What every card, field and menu page of the OpenBMC web interface means, how
you use it, which Redfish request it sends, and whether it does anything on
the BeagleBone. Open it at `https://evb-beaglebone.local/` (see the
[Ubuntu](connecting-from-an-ubuntu-pc.md) or
[Windows](connecting-from-a-windows-pc.md) connection guide).

> **How this was checked.** The menu structure and the Redfish request behind
> each page were read from the web UI's source code (webui-vue, at the exact
> version built into our image, `85248e05`). The "On your BeagleBone" notes
> are what to expect from how this image is built; the pages haven't all been
> clicked through on a real board.

---

## The big picture

* **The BMC is the caretaker's office of a building.** The "building" is the
  server it manages, which the web UI calls the **host** or **server**.
* **The web UI is the front desk**, and **Redfish is the standard request
  form** behind every button: each click sends a Redfish request to `bmcweb`.
  (More in the [Redfish guide](redfish-i2c-sensor/README.md).)
* **The BeagleBone is a caretaker's office with no building attached.** The
  office's own phone, logbook, clock and staff list all work. The switches
  meant for the building (power, screen, boot codes) are wired to nothing.

So the pages fall into two kinds: pages about the **BMC itself** (work) and
pages about the **host** (empty or no effect).

---

## Top bar

| Item | What it means | How you use it | On your BeagleBone |
| --- | --- | --- | --- |
| **Health** ✅ | Overall status: green OK, yellow warning, red critical. Like a car's dashboard warning light. | Read-only. Click for details. | Green: no problems reported |
| **Power** (grey icon) | Is the **host** on or off? | Read-only here; controlled under Operations → Server power operations | Grey (off/unknown): no host |
| **Refresh** | Reloads the page's data from the BMC | Click | Works |
| **root ▾** | Your account menu: **Profile settings** (change your password, show times in UTC or your PC's time zone) and **Log out** | Click | Works |

The **"Not Secure"** in the address bar means the BMC uses a certificate it
made itself, which your browser doesn't recognise. The connection is still
encrypted. You can replace the certificate under Security and access →
Certificates.

---

## Overview page

| Card / field | What it means | How you set it | On your BeagleBone |
| --- | --- | --- | --- |
| **Server information**: Model, Server manufacturer, Serial number | The host's identity, read from its hardware ID chips. Like the label on the back of a laptop. | Read-only | `--`: no host, no inventory data configured |
| **Asset tag** ✎ | **Your own** label for the machine, like the sticker IT puts on a laptop ("LAB-BBB-01") | Click ✎. Redfish: `PATCH /redfish/v1/Systems/system` with `{"AssetTag": "…"}` | May not save: there's no host inventory to store it on |
| **Firmware information**: Running, Backup, Firmware version | OpenBMC normally keeps **two copies** of its firmware on a flash chip, the running one and a backup (like keeping the previous app version in case the new one fails) | Changes only through firmware updates | "none" / `--`: our SD/eMMC image doesn't register itself the way flash-chip images do. Expected. |
| **Network information**: Hostname, Link status, IPv4, DHCPv4 | The BMC's network name, whether the cable is connected, fixed (static) addresses, and the address it got automatically (DHCP) | Settings → Network | Works: hostname `evb-beaglebone`, link up, no static address, and a `10.42.0.x` address from your PC's "Shared" profile |
| **Power information**: Power consumption, Power cap | How many watts the host draws, and an optional upper limit | Cap: Resource management → Power | Not available / Disabled: no host, no power sensor |
| **Event logs**: Critical, Warning | Number of serious and warning entries in the logbook | **Export all** downloads them; **View more** opens the log | 0 / 0 |
| **Inventory and LEDs**: System identify LED | The **"find me" light**: an LED on the server so someone can find it in a big data centre. Like pressing your car key to flash the lights in a car park. | Toggle. Redfish: `LocationIndicatorActive` on `/redfish/v1/Systems/system` | Probably no effect: no identify LED is configured for this board yet |

---

## Logs

| Page | What it is | How you use it | On your BeagleBone |
| --- | --- | --- | --- |
| **Event logs** | The BMC's **logbook**: errors, warnings and notices, with time and severity | Filter, search, export, mark resolved, delete, or **Clear all** (Redfish `LogService.ClearLog`) | Works, nearly empty. With the bmcweb event-log option from the sensor guide, entries created by OpenBMC programs also appear. |
| **POST code logs** | The host's **boot progress codes**. POST = power-on self-test: numbers the BIOS reports at each startup stage, like a pre-flight checklist. Shows where a server got stuck. | Read, export | Empty: no host |
| **Dumps** | **Black-box recorder snapshots** for debugging: a BMC dump collects the BMC's logs and state into one file; a system dump does the same for the host | **Initiate dump** (Redfish `LogService.CollectDiagnosticData`), then download | A BMC dump should work (the dump collector is in the image); system dump: no host |

---

## Hardware status

| Page | What it is | On your BeagleBone |
| --- | --- | --- |
| **Inventory and LEDs** | A parts list (system, BMC, chassis, processors, memory, fans, power supplies), each with its own identify LED | Mostly empty: nothing is described for this board |
| **Sensors** | Every sensor: reading, units, thresholds, status | Empty until sensors are configured ([sensor guide](redfish-i2c-sensor/README.md)) |

---

## Operations

| Page | What it is | How you use it | On your BeagleBone |
| --- | --- | --- | --- |
| **Factory reset** | Put **BMC settings** back to defaults (Redfish `Manager.ResetToDefaults`, `ResetAll`), or reset the **host's BIOS settings** (`Bios.ResetBios`). Like "reset phone to factory settings". | Choose which, confirm | **Avoid**: built for OpenBMC's flash-chip layout, which our image doesn't use. To start clean, re-flash. |
| **KVM** | **K**eyboard, **V**ideo, **M**ouse: see the host's screen and type into it from your browser, even during BIOS. Like remote desktop that works before the operating system starts. | Opens a live screen | Nothing to show: no host video |
| **Key clear** | Clears encryption keys held by the host's firmware. Specific to IBM POWER servers (a Hostboot setting). | Pick a key type, confirm | Not applicable |
| **Firmware** | Upload new firmware for the BMC or host, switch between running and backup copies | Upload an image file, activate it | Won't work for our image (same reason as "Running: none"). Update by re-flashing. |
| **Reboot BMC** | Restarts the **BMC itself**, the BeagleBone (Redfish `Manager.Reset`) | Click, confirm | **Works.** Web and SSH drop for about a minute; afterwards run `nmcli connection up beaglebone` on the PC. |
| **SOL console** | **Serial over LAN**: the host's serial console in your browser, like plugging a serial cable into the server from across the network | Opens a terminal | Nothing connected: no host |
| **Server power operations** | Turn the **host** on or off or restart it (Redfish `ComputerSystem.Reset`: `On`, `GracefulShutdown`, `ForceOff`, `GracefulRestart`, `ForceRestart`), plus boot settings. "Graceful" asks the operating system to shut down; "Force" is like holding the power button. | Buttons | No effect: no host. Would need GPIO wires to a motherboard's power button. |
| **Virtual media** | Give the host a **virtual USB drive or DVD** from a file on your PC (an installer image, say). Like handing the server a USB stick over the network. | Choose a file, **Start** (Redfish `VirtualMedia.InsertMedia` / `EjectMedia`) | Nothing to attach it to |

---

## Settings

| Page | What it is | How you set it | On your BeagleBone |
| --- | --- | --- | --- |
| **Date and time** | The BMC's clock: automatic from internet time servers (**NTP**) or set by hand | Choose NTP and enter servers, or enter date and time | Works. Manual is simplest; NTP may also work through your PC's "Shared" connection (not tried). |
| **Network** | Hostname, DHCP or fixed (static) IP addresses, DNS servers, gateway, MAC address | Edit, save | Works, **but careful**: changing addresses or turning off DHCP can cut your web and SSH connection. Keep the serial terminal handy to undo. |
| **Power restore policy** | What the **host** does when mains power returns after an outage: Always on, Always off, Last state | Choose one | No effect: no host |
| **SNMP alerts** | Send events to a network monitoring system (an "SNMP manager") at an address you enter | Add the manager's IP and port | Only useful with such software; not checked whether the SNMP part is in the image |

---

## Security and access

| Page | What it is | How you use it | On your BeagleBone |
| --- | --- | --- | --- |
| **Sessions** | Everyone currently logged in (web UI or Redfish) | Disconnect a session | Works |
| **LDAP** | Log in with your company's central accounts (Active Directory and similar) instead of users stored on the BMC | Enter the directory server's details | Works only with access to such a server |
| **User management** | Create and delete users, set roles (**Administrator**: everything; **Operator**: operate but not manage users; **ReadOnly**: look only), change passwords, password rules, account lockout | Add or edit users | **Works. Change `root`'s default password here.** |
| **Policies** | Switch access methods on or off: **BMC shell via SSH** (port 22), **Network IPMI**, **HTTP Basic authentication**, plus the **web session timeout** | Toggles | Works, **but careful**: turning off SSH locks you out of SSH; turning off Basic authentication breaks the `curl -u root:…` examples (they'd need session tokens). |
| **Certificates** | The HTTPS certificate (the reason for "Not Secure"), CA certificates for LDAP, and creating a certificate request (CSR) | Upload, replace, generate CSR | Works; only needed if you want the browser warning gone |

---

## Resource management

| Page | What it is | On your BeagleBone |
| --- | --- | --- |
| **Power** | A **power cap**: the most watts the host may draw (like a speed limiter on a car) | No effect: no host |

---

## In short

* **Useful on the board now:** Overview (network card), Event logs, BMC dumps,
  Reboot BMC, Date and time, Network, Sessions, User management, Policies,
  Certificates.
* **Empty until configured:** Sensors, Inventory, the identify LED.
* **Need a real host server:** POST codes, KVM, Key clear, SOL console, Server
  power operations, Virtual media, Power restore policy, power cap.
* **Don't use on this image:** Factory reset and Firmware update. Re-flash
  instead.
