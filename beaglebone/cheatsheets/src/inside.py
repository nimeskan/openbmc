"""Generate 'inside the BMC: programs, D-Bus, bmcweb'.
Usage: python3 inside.py <dir with lib.py> <out dir>"""
import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C
OUT = sys.argv[2]

W, H = 1600, 1690
s = Svg(W, H, 'Inside the BMC: programs, D-Bus and bmcweb')
s.text(W/2, 34, 'Inside the BMC: the programs, the D-Bus that connects them, and bmcweb', size=24, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'The BMC is a small Linux computer running ~30 cooperating programs. They never call each other directly: everything goes as messages over D-Bus.',
       size=14, fill='#555', anchor='middle')
lx = 20
for col, lab in [('teal', 'outside the board'), ('blue', 'OpenBMC programs (in the image)'), ('green', 'added by us'),
                 ('yellow', 'D-Bus itself'), ('purple', 'Linux kernel'), ('grey', 'hardware / reference')]:
    f, st, t = C[col]
    s.raw(f'<rect x="{lx}" y="74" width="22" height="16" rx="3" fill="{f}" stroke="{st}" stroke-width="2"/>')
    s.text(lx + 30, 87, lab, size=13)
    lx += 30 + len(lab) * 6.9 + 24

# ======================================================== part 1: the board
s.text(20, 120, '1. WHAT IS RUNNING ON THE BOARD', size=14, weight='bold', fill='#333')
# outside world
s.box(20, 134, 230, 300, 'teal', 'Your PC / the network', [
    'Browser → web UI', '   (HTTPS, port 443)', 'curl / fleet tools → Redfish', '   (HTTPS, port 443)',
    'ssh → a shell (port 22)', 'ipmitool → IPMI', '   (UDP port 623)', 'mDNS: "evb-beaglebone.local"', '   (avahi, port 5353)'], line_size=12.5)
BX, BW = 270, 1310
s.raw(f'<rect x="{BX}" y="134" width="{BW}" height="700" rx="14" fill="#fafafa" stroke="#333" stroke-width="2.5"/>')
s.text(BX + 14, 156, 'The BeagleBone running OpenBMC (Linux)', size=15, weight='bold', fill='#222')

# front-door programs (talk to the network)
fd = [('bmcweb', 'web server + Redfish API', 'port 443', 'blue'), ('dropbear', 'SSH server → shell', 'port 22', 'blue'),
      ('netipmid (phosphor-ipmi-net)', 'IPMI over the network', 'UDP 623', 'blue'), ('avahi-daemon', 'answers "….local" names', 'port 5353', 'blue')]
x = BX + 14
for name, job, port, col in fd:
    s.box(x, 170, 300, 70, col, name, [job, port], line_size=12, line_gap=15)
    x += 318
s.arrow(250, 205, BX + 12, 205)
s.text(BX - 6, 196, 'network', size=11.5, fill='#555', anchor='end')
s.text(BX + 14, 262, '"Front doors": programs that talk to the outside world. bmcweb turns web/Redfish requests into D-Bus messages (part 3).',
       size=12.5, italic=True, fill='#555')

# D-Bus bar
DY = 300
f, st, t = C['yellow']
s.raw(f'<rect x="{BX+14}" y="{DY}" width="{BW-28}" height="54" rx="10" fill="{f}" stroke="{st}" stroke-width="2.5"/>')
s.text(BX + BW/2, DY + 22, 'D-Bus system bus  (the program dbus-broker; socket /run/dbus/system_bus_socket)', size=14.5, weight='bold', fill=t, anchor='middle')
s.text(BX + BW/2, DY + 42, 'Every program connects to it once, claims a NAME, and from then on sends and receives messages by name. Like a switchboard: all traffic goes through it.',
       size=12.5, fill='#333', anchor='middle')
for i in range(4):
    xx = BX + 14 + 150 + i * 318
    s.line(xx, 240, xx, DY, colour='#d48a00', width=3)

# daemons grid
dm = [
    ('phosphor-state-manager ×3', 'xyz.openbmc_project.State.Host0 …', 'power states: Host0, Chassis0, BMC', 'blue'),
    ('phosphor-objmgr (mapper)', 'xyz.openbmc_project.ObjectMapper', 'directory: which program owns which object', 'blue'),
    ('phosphor-ledmanager', 'xyz.openbmc_project.LED.GroupManager', 'LED groups (identify, booted …)', 'blue'),
    ('phosphor-led-sysfs', 'xyz.openbmc_project.LED.Controller', 'physical LEDs from /sys/class/leds (idle)', 'blue'),
    ('bbb-led-standin', 'xyz.openbmc_project.LED.GpioStandIn', 'our 4 physical LEDs via GPIO', 'green'),
    ('phosphor-log-manager', 'xyz.openbmc_project.Logging', 'event log entries', 'blue'),
    ('phosphor-networkd', 'xyz.openbmc_project.Network', 'IP/DHCP settings for web UI + Redfish', 'blue'),
    ('phosphor-user-manager', 'xyz.openbmc_project.User.Manager', 'BMC user accounts, roles', 'blue'),
    ('phosphor-inventory-manager', 'xyz.openbmc_project.Inventory.Manager', 'parts list (FRUs)', 'blue'),
    ('phosphor-settings-manager', 'xyz.openbmc_project.Settings', 'saved settings (power policy …)', 'blue'),
    ('phosphor-time-manager', 'xyz.openbmc_project.Time.Manager', 'NTP or manual time', 'blue'),
    ('phosphor-software-manager', 'xyz.openbmc_project.Software.Manager', 'firmware versions + updates', 'blue'),
    ('phosphor-debug-collector', 'xyz.openbmc_project.Dump.Manager', 'BMC dumps', 'blue'),
    ('telemetry', 'xyz.openbmc_project.Telemetry', 'Redfish metric reports', 'blue'),
    ('phosphor-health-monitor', 'xyz.openbmc_project.HealthMon', 'BMC CPU/memory/storage health', 'blue'),
    ('systemd (+ networkd, timedated …)', 'org.freedesktop.systemd1 …', 'starts/stops all programs; Linux services', 'blue'),
]
cols, cw, ch = 4, 312, 72
gx, gy = BX + 14, DY + 84
rows_n = (len(dm) + cols - 1) // cols
for c in range(cols):
    x = gx + c * (cw + 6)
    s.line(x + cw/2, DY + 54, x + cw/2, gy + (rows_n - 1) * (ch + 34) + 4, colour='#d48a00', width=2.5)
for i, (prog, bus, job, col) in enumerate(dm):
    x = gx + (i % cols) * (cw + 6)
    y = gy + (i // cols) * (ch + 34)
    s.box(x, y, cw, ch, col, prog, [(bus, True, False), job], line_size=11.4, title_size=13, line_gap=16)
s.text(BX + 14, DY + 84 + 4 * (ch + 34) + 4, 'Orange lines = each program\'s connection to D-Bus, labelled in its box with the NAME it claimed. 26 programs in our image claim a name.',
       size=12.5, italic=True, fill='#555')

# kernel + hw
s.box(20, 852, 1560, 54, 'purple', None, [], rx=10)
s.rich(800, 885, [('Linux kernel', False, True), ('  —  programs reach hardware only through it: /dev/gpiochip0, /dev/i2c-2, /sys, network sockets … (see the kernel cheat sheet)', False, False)], size=13.5, anchor='middle')
s.box(20, 914, 1560, 40, 'grey', None, [], rx=10)
s.text(800, 940, 'Hardware: AM335x processor, eMMC, Ethernet, GPIO pins + LEDs, I2C buses, USB …', size=13.5, anchor='middle')

# ======================================================== part 2: D-Bus anatomy
y0 = 984
s.text(20, y0, '2. WHAT IS ON D-BUS: names → objects → interfaces → properties / methods / signals', size=14, weight='bold', fill='#333')
f, st, t = C['yellow']
s.raw(f'<rect x="20" y="{y0+12}" width="770" height="378" rx="12" fill="{f}" stroke="{st}" stroke-width="2"/>')
lines = [
    (0, 'BUS NAME', 'xyz.openbmc_project.State.Host0', 'which program (claimed by phosphor-host-state-manager)'),
    (1, 'OBJECT PATH', '/xyz/openbmc_project/state/host0', 'which thing; paths form a tree like folders'),
    (2, 'INTERFACE', 'xyz.openbmc_project.State.Host', 'a named set of features (YAML in phosphor-dbus-interfaces)'),
    (3, 'PROPERTY', 'CurrentHostState  (s) = "…HostState.Off"', 'a value: read with Get, watch for changes'),
    (3, 'PROPERTY', 'RequestedHostTransition  (s)', 'writable: Set it to ask for power on/off'),
    (3, 'METHOD', '(e.g. ObjectMapper: GetObject(path, ifaces))', 'an action you call; returns a reply'),
    (3, 'SIGNAL', 'PropertiesChanged', 'a broadcast: "this value just changed"'),
    (2, 'INTERFACE', 'org.freedesktop.DBus.Properties', 'standard on every object: Get / Set / GetAll'),
    (2, 'INTERFACE', 'org.freedesktop.DBus.Introspectable', 'standard: "describe yourself" (XML)'),
]
yy = y0 + 42
for depth, kind, val, note in lines:
    xx = 36 + depth * 26
    if kind:
        s.text(xx, yy, kind, size=11.5, weight='bold', fill=t)
        s.text(xx + 96, yy, val, size=12.2, mono=True, weight='bold')
    s.text(xx + 96, yy + 15, note, size=11.5, italic=True, fill='#555')
    yy += 33
s.text(36, y0 + 372, 'Types are one letter: s string, b bool, y byte, q uint16, i int32, u uint32, x int64, d double, a… array, v variant.', size=11.8, fill='#333')

# message
s.box(810, y0 + 12, 770, 378, 'grey', 'One message, as it travels over the bus', [], title_size=14)
msg = [('type', 'method_call'), ('sender', ':1.42   (e.g.: the unique ID D-Bus gave bmcweb)'),
       ('destination', 'xyz.openbmc_project.State.Host0'), ('path', '/xyz/openbmc_project/state/host0'),
       ('interface', 'org.freedesktop.DBus.Properties'), ('member', 'Set'), ('signature', 'ssv'),
       ('body', '"xyz.openbmc_project.State.Host",'), ('', '"RequestedHostTransition",'),
       ('', '<s "xyz.openbmc_project.State.Host.Transition.On">')]
yy = y0 + 62
for k, v in msg:
    s.text(830, yy, k, size=12, weight='bold', fill='#7a4d00', mono=True)
    s.text(960, yy, v, size=12, mono=True)
    yy += 19
s.text(830, yy + 8, '→ dbus-broker delivers it to the program that owns the destination name;', size=12, fill='#333')
s.text(830, yy + 26, '   that program replies (method_return, or error) to :1.42.', size=12, fill='#333')
s.text(830, yy + 50, 'Same thing typed by hand:', size=12, weight='bold')
s.text(830, yy + 68, 'busctl set-property xyz.openbmc_project.State.Host0 \\', size=11.5, mono=True)
s.text(830, yy + 84, '  /xyz/openbmc_project/state/host0 xyz.openbmc_project.State.Host \\', size=11.5, mono=True)
s.text(830, yy + 100, '  RequestedHostTransition s xyz.openbmc_project.State.Host.Transition.On', size=11.5, mono=True)

# ======================================================== part 3: bmcweb
y0 = 1394
s.text(20, y0, '3. BMCWEB: THE TRANSLATOR BETWEEN THE WEB AND D-BUS', size=14, weight='bold', fill='#333')
s.box(20, y0 + 12, 330, 196, 'teal', 'HTTPS request (JSON)', [
    ('GET /redfish/v1/Systems/system', True, False), '', ('PATCH /redfish/v1/Systems/system', True, False),
    ('{"LocationIndicatorActive": true}', True, False), '', ('POST …/Actions/ComputerSystem.Reset', True, False),
    ('{"ResetType": "On"}', True, False)], line_size=11.8)
s.arrow(352, y0 + 110, 392, y0 + 110)
s.box(394, y0 + 12, 400, 196, 'blue', 'bmcweb', [
    'checks login + permissions (user roles),', 'finds the handler for that URL,',
    'makes the D-Bus calls it needs (often several,', 'asking the mapper first who owns what),',
    'waits for the replies, then builds the', 'Redfish JSON answer.',
    (('Redfish shape: DMTF standard. D-Bus side: OpenBMC.', False, True))], line_size=12.2)
s.arrow(796, y0 + 110, 836, y0 + 110)
s.box(838, y0 + 12, 742, 196, 'yellow', 'D-Bus calls it makes (examples)', [
    (('GET  → ', False, True), ('Get CurrentHostState', True, False), (' on State.Host0  → "PowerState": "Off"', False, False)),
    (('       ', False, False), ('Get Asserted', True, False), (' on …/groups/enclosure_identify_blink  → "LocationIndicatorActive"', False, False)),
    (('       ', False, False), ('GetSubTree', True, False), (' (mapper) + ', False, False), ('GetAll', True, False), (' on inventory  → Model, SerialNumber …', False, False)),
    (('PATCH → ', False, True), ('Set Asserted = true', True, False), (' on …/groups/enclosure_identify_blink', False, False)),
    (('POST  → ', False, True), ('Set RequestedHostTransition = …Transition.On', True, False), (' on State.Host0', False, False)),
    '',
    (('The web UI is just files bmcweb serves (webui-vue, in JavaScript); ', False, False), ('it', False, True), (' calls Redfish too.', False, False)),
], line_size=12.2, line_gap=21)

s.box(20, y0 + 222, 1560, 60, 'grey', None, [], rx=10)
s.rich(36, y0 + 246, [('See it on the board:  ', False, True), ('busctl list', True, False), (' (all names)   ', False, False), ('busctl tree xyz.openbmc_project.State.Host0', True, False),
                       ('   ', False, False), ('busctl introspect <name> <path>', True, False), ('   ', False, False), ('busctl get-property …', True, False)], size=12.5)
s.rich(36, y0 + 268, [('Watch it live:  ', False, True), ('busctl monitor', True, False), (' — then click the identify switch in the web UI and see bmcweb\'s Set, the LED manager\'s mapper call and the stand-in\'s property writes scroll past.', False, False)], size=12.5)
s.save(f'{OUT}/openbmc-inside.svg')
