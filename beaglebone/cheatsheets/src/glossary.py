"""Add a "Words on this sheet" glossary strip to the bottom of an SVG diagram.

Usage (also called by the generator scripts after they write a sheet):
    python3 glossary.py file.svg [file.svg ...]

The strip is a <g id="glossary"> group; running this again replaces it,
so it is safe to re-run. Definitions are kept here, one list per file name.
"""
import os
import re
import sys
from xml.sax.saxutils import escape

FONT = 'Helvetica, Arial, sans-serif'

G = {
# ---------------------------------------------------------------- cheat sheets
'linux-folders.svg': [
    ('partition', 'a separate, separately formatted section of a disk; our eMMC has p1 (/boot), p2 (/) and optionally p3 (/data)'),
    ('file system (ext4, FAT)', 'the format files are stored in on a partition. ext4 = Linux\'s usual one; FAT = a simple one U-Boot can read'),
    ('mount', 'attach a partition (or a pretend file system) to a folder so its files appear there. `mount` lists them; /etc/fstab says what to mount at boot'),
    ('symlink ("shortcut")', 'a file that points to another path, e.g. /lib → /usr/lib. ls -l shows it with an arrow'),
    ('tmpfs', 'a file system kept in RAM: fast, but empty after every reboot (/run, /tmp)'),
    ('daemon / service', 'a program that runs in the background (bmcweb, the LED manager …), started by systemd'),
    ('unit file', 'systemd\'s small text file describing one service or target (see the systemd sheet)'),
    ('kernel module (.ko)', 'a piece of kernel code (often a driver) loaded into the running kernel when needed'),
    ('device file (/dev)', 'a special file that stands for a driver; programs open it to talk to hardware'),
    ('PID', 'process ID: the number Linux gives each running program'),
    ('re-flash', 'writing the whole image onto the eMMC again: replaces everything on p1 and p2'),
    ('MLO / U-Boot / zImage / .dtb', 'boot-loader stages, the compressed kernel, and the board\'s hardware description (see the SD card boot diagram)'),
],
'kernel-drivers-modules.svg': [
    ('user space / kernel space', 'two privilege levels of the CPU: programs run in user space and must ask the kernel to touch hardware'),
    ('system call', 'a function call into the kernel (open, read, write, ioctl …); the CPU switches into kernel mode to run it'),
    ('ioctl', '"I/O control": a system call for device-specific requests, each identified by a number (a "request code")'),
    ('driver', 'kernel code that knows how to operate one kind of hardware (registers, interrupts)'),
    ('subsystem', 'a generic kernel layer for one kind of device (gpiolib for GPIO, I2C core …) that drivers plug into'),
    ('device tree / compatible', 'the board\'s hardware description (.dtb). Each node\'s "compatible" string is how the kernel picks its driver'),
    ('probe()', 'the driver function the kernel calls when it matches a device; it sets the hardware up and registers it'),
    ('register', 'a memory address inside a chip block that controls or reports hardware (e.g. 0x4804C194)'),
    ('PMIC', 'power-management chip: makes the board\'s supply voltages (the TPS65217 on the BeagleBone)'),
    ('hwmon', 'the kernel\'s framework for monitoring sensors (temperatures, voltages …): /sys/class/hwmon'),
    ('cpsw / musb / MMC', 'the AM335x\'s Ethernet, USB and SD/eMMC controllers (and their drivers)'),
    ('struct gpio_chip', 'the "table of functions" a GPIO driver fills in so gpiolib can call it'),
],
'systemd-units-services.svg': [
    ('PID 1', 'the first program the kernel starts; on our board that is systemd, and it starts everything else'),
    ('daemon', 'a program that runs in the background, waiting to do work (bmcweb, phosphor-ledmanager …)'),
    ('port', 'a number that identifies a network service on a machine: 22 = SSH, 443 = HTTPS'),
    ('journal / journalctl', 'systemd\'s log store, and the command to read it (journalctl -u <unit> -b)'),
    ('udev', 'the program that reacts when the kernel finds a device: creates /dev entries, can start units'),
    ('drop-in', 'a small file X.service.d/*.conf that changes a few lines of a unit without copying the whole file'),
    ('D-Bus name (BusName=)', 'the name a program claims on D-Bus, e.g. xyz.openbmc_project.LED.GpioStandIn (see the D-Bus sheet)'),
    ('mapper wait', 'OpenBMC command that waits until the object mapper knows a D-Bus object'),
    ('ROM → MLO → U-Boot', 'the boot stages before Linux (see the SD card boot diagram)'),
    ('enabled vs started', 'enabled = will start at every boot (a link in a .wants folder); started = running now'),
],
'usb-gadget.svg': [
    ('enumeration', 'when a device is plugged in, the host asks it what it is (reads its descriptors) and picks a driver'),
    ('descriptors', 'data a USB device sends about itself: class, endpoints, product name, IDs'),
    ('endpoint', 'one data channel of a USB device, in one direction (IN = to the host, OUT = from the host)'),
    ('class driver', 'a generic host-side driver chosen by the device\'s class (cdc_ncm on Linux, UsbNcm.sys on Windows)'),
    ('UDC', 'USB Device Controller: the hardware (and its driver) that lets a computer act as a USB device'),
    ('function', 'one capability of a gadget: network (ncm), serial (acm), storage …'),
    ('libcomposite', 'kernel helper that combines one or more functions into one USB device'),
    ('configfs', 'a pretend file system (/sys/kernel/config) where you build a gadget with mkdir and echo'),
    ('PHY', 'the part of the chip that drives the actual USB wires (signal levels, timing)'),
    ('DMA (CPPI 4.1)', 'hardware that copies data between memory and the controller without the CPU'),
    ('dr_mode', 'device-tree setting for a USB port: host, peripheral (= device) or otg (either)'),
    ('CDC / NCM / ACM', 'USB "communications" classes: NCM = network adapter, ACM = serial port'),
],
'gpio-toggle-c-layers.svg': [
    ('file descriptor (fd)', 'the number a program gets back from open(); later calls (ioctl, close) use it'),
    ('line handle', 'a NEW fd the kernel returns when lines are reserved; holding it open = owning the lines'),
    ('ioctl request code', 'number naming the request, e.g. 0xC250B407 = direction + structure size + type 0xB4 (GPIO) + command 7'),
    ('syscall number', 'number that tells the kernel which system call (ioctl = #54); "svc #0" is the ARM instruction to enter the kernel'),
    ('v1 / v2', 'two generations of the kernel\'s GPIO interface; libgpiod 1.6 uses v1, our Path A uses v2; both are enabled'),
    ('gc->request() …', 'a call through the table of functions the driver gave gpiolib (struct gpio_chip)'),
    ('pm_runtime', 'kernel power management: turns a hardware block\'s clock on while something uses it'),
    ('spinlock', 'a lock that stops two CPUs or an interrupt changing the same register at the same time'),
    ('OE / DATAOUT', 'GPIO1 registers: OE = direction (0 = output), DATAOUT = output values; SET/CLEARDATAOUT change single bits'),
    ('pad mux', 'per-pin register choosing which job a pin has; mode 7 = GPIO (0x44E10860 for USR3)'),
    ('VFS', 'the kernel\'s file layer: routes open/ioctl on /dev/gpiochip0 to the GPIO character-device code'),
    ('EBUSY', 'error "device or resource busy": another program or driver already owns the line'),
],
'gpio-toggle-cpp-layers.svg': [
    ('RAII', 'C++ rule: an object owns a resource and its destructor releases it (Fd closes its fd automatically)'),
    ('destructor (~Fd)', 'function C++ runs automatically when an object goes out of scope, even during an exception'),
    ('exception', 'C++ error that jumps to the nearest catch, cleaning up objects on the way; here std::system_error carries errno'),
    ('std::optional', 'a value that may be missing (find_line returns "nothing" if the line isn\'t found)'),
    ('shared_ptr', 'reference-counted owner; libgpiod\'s chip is closed when the last copy goes away'),
    ('libgpiodcxx', 'libgpiod\'s C++ part (gpiod.hpp): classes wrapping the C library'),
    ('file descriptor / line handle', 'as in the C sheet: open() returns an fd; reserving lines returns a new fd that owns them'),
    ('ioctl / syscall / v1 / v2', 'as in the C sheet: the request codes and system calls are identical in C++'),
    ('pm_runtime / spinlock', 'kernel power management (clock on while used) and a lock protecting registers'),
    ('OE / DATAOUT / pad mux', 'GPIO1 direction and value registers, and the pin-function register (mode 7 = GPIO)'),
],
'leds-architecture.svg': [
    ('LED group', 'a named situation (identify, BMC booted …) listing which LEDs do what; turning it on = Asserted = true'),
    ('physical LED object', 'one real LED on D-Bus, with State (Off/On/Blink), DutyOn (%) and Period (ms)'),
    ('Priority', 'which state wins when two active groups want the same LED differently'),
    ('object mapper', 'OpenBMC\'s directory of which program owns which D-Bus object (GetObject answers "who serves X?")'),
    ('bus name', 'the name a program claims on D-Bus, e.g. xyz.openbmc_project.LED.GroupManager'),
    ('stand-in', 'our temporary program doing phosphor-led-sysfs\'s job until the kernel has an LED driver'),
    ('Type=dbus', 'a systemd unit counts as "started" once its program has claimed its D-Bus name'),
    ('ioctl / line handle', 'the system call and the held file descriptor the stand-in uses to drive the GPIO lines'),
    ('(y) (q) (s) (b)', 'D-Bus type letters: byte, 16-bit unsigned, string, boolean'),
    ('Redfish / bmcweb', 'the standard web API for managing servers, and OpenBMC\'s server for it (port 443)'),
],
'leds-sequences.svg': [
    ('Properties.Set', 'the standard D-Bus method to change a property on another program\'s object'),
    ('GetObject', 'object-mapper method: "which program owns this object path?"'),
    ('Asserted', 'an LED group\'s on/off property'),
    ('DutyOn / Period', 'blink settings: % of each cycle the LED is on; cycle length in ms'),
    ('introspect', 'ask a program to describe its objects (the mapper does this for every new name)'),
    ('mapper wait', 'command that waits until the mapper knows an object (used so start-up happens in the right order)'),
    ('multi-user.target', 'systemd\'s "system is fully up" milestone; bmc_booted is asserted right after it'),
    ('ioctl SET_VALUES', 'the GPIO system call that changes the level of lines the program holds'),
    ('DATAOUT', 'the GPIO1 register holding the output levels (bit 21 = USR0, bit 24 = USR3)'),
    ('HTTP 2xx', 'success status codes (200 OK, 204 No Content)'),
],
'openbmc-targets.svg': [
    ('host', 'the main server computer the BMC looks after: its CPUs and operating system. Our BeagleBone has no host'),
    ('chassis', 'the server\'s box and main power supply; "chassis on" = the main power rails are on'),
    ('BMC', 'the management controller itself (our BeagleBone): it stays powered while the host is off'),
    ('transition', 'a requested change: On, Off, Reboot, PowerCycle …'),
    ('target', 'systemd milestone that groups units; "starting" it starts everything hooked into it'),
    ('graceful vs force', 'graceful = ask the operating system to shut down first; force = cut or cycle power at once'),
    ('soft power off', 'asking the host\'s operating system to shut itself down (via IPMI or PLDM messages)'),
    ('warm reboot', 'restart the host\'s operating system without switching chassis power off'),
    ('quiesce', 'stop and HOLD the host in a safe state (no automatic reboot) so people can collect debug information'),
    ('watchdog', 'timer the host must keep resetting; if it stops, the host is assumed hung (host-timeout)'),
    ('blackout', 'chassis power was lost unexpectedly (e.g. mains power cut)'),
    ('IPMI / KCS', 'IPMI = older management protocol (ipmitool); KCS = the host-to-BMC hardware channel it uses'),
    ('POH', 'power-on hours: a counter of how long the chassis has been powered'),
    ('@0', 'instance number: chassis 0 / host 0 (a server can have several)'),
],
'openbmc-inside.svg': [
    ('daemon', 'a program that runs in the background, waiting to do work'),
    ('port', 'number of a network service on a machine: 443 HTTPS, 22 SSH, 623 IPMI, 5353 mDNS'),
    ('Redfish', 'the industry-standard (DMTF) web API for managing servers: URLs that return JSON'),
    ('IPMI', 'an older management protocol, still common (the ipmitool command)'),
    ('SSH', 'secure remote shell: log in and type commands (dropbear is the SSH server on our board)'),
    ('mDNS', 'lets machines on a local network find each other by name ("evb-beaglebone.local") without a DNS server'),
    ('bus name / object path / interface', 'who (which program), which thing (a path), which set of features (see the D-Bus sheet)'),
    ('unique name (:1.42)', 'the ID D-Bus gives each connection; well-known names like xyz.openbmc_project.… point to one'),
    ('FRU', 'field-replaceable unit: a part you can swap (fan, power supply, board), listed in the inventory'),
    ('event log', 'the BMC\'s list of notable events and errors, shown in the web UI and Redfish'),
    ('variant <s …>', 'a D-Bus value that carries its own type letter (s = string)'),
    ('webui-vue', 'OpenBMC\'s web UI: JavaScript files served by bmcweb that run in your browser and call Redfish'),
],
'dbus-explained.svg': [
    ('process / PID', 'a running program, and the number Linux gives it; each has its own private memory'),
    ('socket', 'a two-way connection between programs; the socket FILE is only the address used to open one'),
    ('dbus-broker', 'the program that implements the D-Bus system bus (OpenBMC uses it instead of the older dbus-daemon)'),
    ('well-known name', 'a fixed name like xyz.openbmc_project.State.Host0 that a program claims; it points to its unique name'),
    ('unique name', 'the ID the broker gives each connection: :1.17, :1.42 …'),
    ('object / interface / property', 'a thing a program publishes, a named set of features on it, and a value in that set'),
    ('event loop', 'a program\'s main loop: it sleeps until a message, timer or signal arrives, then handles it'),
    ('match rule', 'a subscription telling the broker which signals a program wants to receive'),
    ('policy (.conf)', 'XML rules saying who may own a name or call whom (/usr/share/dbus-1/system.d/)'),
    ('busctl', 'systemd\'s command-line D-Bus tool: list, tree, introspect, get-property, call, monitor'),
],
'openbmc-programs.svg': [
    ('FRU', 'field-replaceable unit: a swappable part (fan, power supply, board) with an ID memory'),
    ('KCS / BT', 'hardware channels between the host and the BMC used by IPMI (our board has none)'),
    ('introspect', 'ask a program to describe its objects; the mapper does this to build its directory'),
    ('quiesced', 'host stopped and held in a safe state for debugging, without automatic reboot'),
    ('POH', 'power-on hours counter'),
    ('PAM', 'Linux\'s pluggable login system: rule files for password quality, lockout, history'),
    ('udev', 'program that reacts to the kernel finding devices; tells phosphor-led-sysfs about new LEDs'),
    ('NTP', 'network time protocol: setting the clock from a time server'),
    ('flash', 'the memory chip most BMCs boot from; our BeagleBone uses an SD card / eMMC instead'),
    ('hwmon / sensor / threshold', 'kernel sensor framework; a measured value on D-Bus; warning/critical limits on it'),
    ('dump', 'an archive of logs and state collected for debugging'),
    ('metric report', 'Redfish telemetry: sensor values sampled on a schedule, with min/max/average'),
],
# ---------------------------------------------------------------- build diagrams
'overview.svg': [
    ('BitBake / layers', 'the build tool, and the folders of recipes and settings it combines into an image'),
    ('image (.wic.xz)', 'one file containing the whole SD card (partitions and all), compressed with xz'),
    ('GitHub Actions / Releases', 'GitHub\'s build servers, and the download page where the finished image is published'),
    ('balenaEtcher / dd / bmaptool', 'programs that write an image file onto an SD card'),
    ('U-Boot / systemd', 'the boot loader that starts Linux, and the first program that starts all others'),
    ('Redfish / IPMI / SSH', 'standard web API for servers / older management protocol / remote command line'),
],
'layers.svg': [
    ('layer', 'a folder of recipes and settings (meta-…); higher layers can add to or override lower ones'),
    ('recipe (.bb)', 'instructions for fetching, building and packaging one piece of software'),
    ('machine / distro', 'which board to build for (evb-beaglebone) / which OS flavour and policies (openbmc-phosphor)'),
    ('image recipe', 'the recipe that lists everything to put on the card (obmc-phosphor-image)'),
    ('bblayers.conf / local.conf', 'your build\'s list of layers / your build\'s settings'),
    ('rm_work', 'setting that deletes each recipe\'s temporary build files when done, to save disk space'),
    ('OpenEmbedded-Core', 'the base set of recipes shared by all Yocto-based builds'),
],
'sdcard-boot.svg': [
    ('partition table (MBR)', 'the first sector of the card: says where each partition starts and ends'),
    ('FAT / ext4', 'two file-system formats: FAT is simple (the boot ROM and U-Boot read it), ext4 is Linux\'s usual'),
    ('Boot ROM', 'code built into the AM335x chip; looks for MLO on the eMMC, or the SD card when S2 is held'),
    ('MLO (SPL)', 'tiny first-stage loader: sets up RAM, then loads U-Boot'),
    ('U-Boot / extlinux.conf', 'the boot loader, and its menu file naming the kernel, device tree and kernel options'),
    ('zImage / .dtb', 'the compressed Linux kernel / the board\'s hardware description'),
    ('S2 button', 'the "boot" button near the SD slot: hold it at power-on to boot from the SD card'),
    ('serial console', 'text terminal over the 6-pin J1 header (3.3 V USB-serial adapter, 115200 baud)'),
],
'ci-pipeline.svg': [
    ('runner', 'a fresh virtual machine GitHub gives each run (max 6 hours, limited disk)'),
    ('sstate-cache', 'BitBake\'s store of already-built results; reusing it skips work on the next run'),
    ('cache storage', 'GitHub\'s per-repository cache (actions/cache); unused entries are deleted after 7 days'),
    ('workflow / gh workflow run', 'the build recipe file for GitHub Actions / the command that starts a new run'),
    ('artifact', 'files a run uploads for download (here: build logs when something really failed)'),
    ('release', 'a GitHub download page with files (.wic.xz, .wic.bmap, SHA256SUMS checksums)'),
],
# ---------------------------------------------------------------- Redfish guide
'architecture.svg': [
    ('PLANNED, not in our image yet', 'entity-manager and externalsensor (dbus-sensors) come with the planned rebuild; the rest exists today'),
    ('entity-manager', 'reads JSON board descriptions and publishes what hardware is present on D-Bus'),
    ('externalsensor', 'dbus-sensors program that hosts sensors whose values another program writes'),
    ('association', 'a D-Bus link between objects (sensor ↔ chassis) that the mapper indexes'),
    ('i2cget / busctl', 'command-line tools: read an I2C register / call or set things on D-Bus'),
    ('Redfish JSON', 'the web API\'s answer format: names and values in braces'),
],
'redfish-request.svg': [
    ('X-Auth-Token', 'session token sent with each request after logging in (instead of the password)'),
    ('GetSubTree', 'object-mapper method: list objects under a path that have given interfaces'),
    ('association endpoints', 'objects linked to this one (here: all sensors of the board)'),
    ('GetAll', 'standard D-Bus method returning all properties of one interface'),
],
'redfish-tree.svg': [
    ('resource', 'one JSON document at one URL (a system, a sensor …)'),
    ('collection', 'a resource listing links to its members (e.g. Sensors)'),
    ('@odata.id', 'the URL of a resource, included in its own JSON so clients can follow links'),
    ('service root', '/redfish/v1: the starting point every client begins from'),
],
'startup-sequence.svg': [
    ('Probe', 'entity-manager rule deciding whether a JSON board description applies ("TRUE" = always)'),
    ('Configuration.ExternalSensor', 'D-Bus object entity-manager publishes describing a sensor for externalsensor to create'),
    ('association "chassis"', 'link from the sensor to its board, so Redfish lists it under that chassis'),
    ('busctl set-property … Value d 25', 'writes the sensor value 25 (d = double, a floating-point number)'),
],
'wiring.svg': [
    ('SCL / SDA', 'I2C\'s two wires: clock and data'),
    ('GND / VCC', 'ground (0 V) and the supply voltage (3.3 V from the BeagleBone)'),
    ('pull-up resistor', 'resistor that holds an I2C line high when nobody pulls it low (I2C needs them)'),
    ('I2C address (0x48)', 'the 7-bit number a chip answers to on its bus; two chips on one bus need different addresses'),
    ('3.3 V logic', 'the pins\' signal level; 5 V signals can damage the AM335x'),
    ('cape EEPROM', 'ID memory chip on BeagleBone add-on boards ("capes"), at 0x54–0x57'),
],
}


def _wrap(text, width_chars):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w) if cur else w
    if cur:
        lines.append(cur)
    return lines


def apply(path):
    name = os.path.basename(path)
    entries = G.get(name)
    if not entries:
        return False
    svg = open(path, encoding='utf-8').read()
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg)
    W, H = float(m.group(1)), float(m.group(2))
    old = re.search(r'<g id="glossary" data-orig-h="(\d+(?:\.\d+)?)">', svg)
    if old:   # already has a strip: remove it and restore the original height
        H = float(old.group(1))
        svg = re.sub(r'\s*<g id="glossary".*?</g><!-- /glossary -->', '', svg, flags=re.S)
        svg = svg.replace(m.group(0), f'viewBox="0 0 {m.group(1)} {H:g}"', 1)
        svg = re.sub(r'(<rect width="%s" height=")%s(")' % (re.escape(m.group(1)), re.escape(m.group(2))),
                     lambda mm: f'{mm.group(1)}{H:g}{mm.group(2)}', svg, count=1)
        m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg)
    cols = 3 if W >= 1400 else 2
    pad, gap = 20, 16
    colw = (W - 2 * pad - (cols - 1) * gap) / cols
    size, lh = 12.0, 15.5
    chars = int((colw - 16) / (size * 0.52))
    # lay entries out column by column, balancing heights
    blocks = []
    for term, text in entries:
        tl = _wrap(term + ' — ' + text, chars)
        blocks.append((term, tl))
    total = sum(len(b[1]) for b in blocks) + len(blocks) * 0.5
    target = total / cols
    columns, cur, acc = [[] for _ in range(cols)], 0, 0.0
    for b in blocks:
        h = len(b[1]) + 0.5
        if acc + h / 2 > target and cur < cols - 1 and columns[cur]:
            cur, acc = cur + 1, 0.0
        columns[cur].append(b)
        acc += h
    rows = max(sum(len(b[1]) + 0.5 for b in c) for c in columns)
    top = int(H) + 6
    box_h = 40 + rows * lh + 8
    out = [f'<g id="glossary" data-orig-h="{H:g}">',
           f'<rect x="{pad}" y="{top}" width="{W - 2 * pad}" height="{box_h}" rx="10" fill="#ffffff" stroke="#888" stroke-width="1.5"/>',
           f'<text x="{pad + 12}" y="{top + 22}" font-family="{FONT}" font-size="14" font-weight="bold" fill="#333">Words on this sheet</text>']
    for ci, col in enumerate(columns):
        x = pad + 12 + ci * (colw + gap)
        y = top + 44
        for term, tl in col:
            for li, line in enumerate(tl):
                if li == 0 and line.startswith(term + ' — '):
                    rest = line[len(term) + 3:]
                    out.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="#333" xml:space="preserve">'
                               f'<tspan font-weight="bold">{escape(term)}</tspan> — {escape(rest)}</text>')
                else:
                    out.append(f'<text x="{x + (0 if li == 0 else 10)}" y="{y}" font-family="{FONT}" font-size="{size}" fill="#333" '
                               f'xml:space="preserve">{escape(line)}</text>')
                y += lh
            y += lh * 0.5
    out.append('</g><!-- /glossary -->')
    newH = int(round(top + box_h + 14))
    svg = svg.replace(m.group(0), f'viewBox="0 0 {m.group(1)} {newH:g}"', 1)
    # stretch a full-size white background rect, if the file has one
    svg = re.sub(r'(<rect width="%s" height=")%s(")' % (re.escape(m.group(1)), re.escape(m.group(2))),
                 lambda mm: f'{mm.group(1)}{newH:g}{mm.group(2)}', svg, count=1)
    svg = svg.replace('</svg>', '\n  ' + '\n  '.join(out) + '\n</svg>')
    open(path, 'w', encoding='utf-8').write(svg)
    return True


if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(('glossary added: ' if apply(p) else 'no glossary for: ') + p)
