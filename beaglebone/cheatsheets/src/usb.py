import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C
W, H = 1240, 1000
s = Svg(W, H, 'USB host, device and gadget cheat sheet')
s.text(W/2, 34, 'USB: host, device and "gadget"', size=24, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'USB is one-sided: the HOST is in charge, the DEVICE answers. Linux "gadget" = Linux acting as the device. Example: USB networking (g_ncm).',
       size=14, fill='#555', anchor='middle')

# --- ports strip ---
s.box(20, 80, 1200, 96, 'grey', 'Our BeagleBone has both kinds of port', [])
s.box(40, 112, 560, 54, 'blue', None, [], rx=8)
s.rich(56, 135, [('USB-A socket (USB1) = HOST', False, True), ('   the board is in charge:', False, False)], size=13.5)
s.text(56, 155, 'plug a memory stick, keyboard, USB-serial adapter INTO the board.  dr_mode = "host"', size=12.5)
s.box(620, 112, 580, 54, 'green', None, [], rx=8)
s.rich(636, 135, [('Mini-USB (USB0) = DEVICE', False, True), ('   the PC is in charge:', False, False)], size=13.5)
s.text(636, 155, 'the board becomes a USB gadget for the PC (network, serial, disk).  dr_mode = "peripheral"', size=12.5)

# --- two stacks ---
top = 196
s.text(300, top + 6, 'PC  =  USB HOST', size=16, weight='bold', fill='#1d3b8a', anchor='middle')
s.text(940, top + 6, 'BEAGLEBONE  =  USB DEVICE ("gadget")', size=16, weight='bold', fill='#1c5e2e', anchor='middle')
hx, hw = 80, 440
dx, dw = 700, 480
rows_h = [
    ('blue', 'Programs', ['ssh root@192.168.7.2   browser   curl']),
    ('blue', 'Network stack', ['new network adapter, gets 192.168.7.1xx by DHCP']),
    ('blue', 'Class driver (picks by USB class)', ['Linux: cdc_ncm      Windows: UsbNcm.sys']),
    ('blue', 'USB host core + host controller driver', ['enumerates the device, reads its descriptors']),
    ('grey', 'USB host controller (hardware)', ['the PC\'s USB port']),
]
rows_d = [
    ('green', 'Programs / daemons', ['dropbear (SSH)   bmcweb (web UI)   avahi']),
    ('green', 'Network stack: interface usb0', ['192.168.7.2 + DHCP server (systemd-networkd)']),
    ('purple', 'Gadget driver + function', ['g_ncm (legacy) or configfs  →  usb_f_ncm, u_ether']),
    ('purple', 'libcomposite + UDC core (generic)', ['assembles functions into one USB device']),
    ('purple', 'UDC driver: musb core + musb_dsps glue', ['Mentor MUSB controller, TI wrapper, CPPI DMA']),
    ('grey', 'USB device controller (hardware)', ['AM335x USB0 → mini-USB socket']),
]
y = top + 22
for col, t, ls in rows_h:
    s.box(hx, y, hw, 64, col, t, ls, center=True)
    y += 82
yh_end = y - 82 + 64
y = top + 22
for col, t, ls in rows_d:
    s.box(dx, y, dw, 64, col, t, ls, center=True)
    y += 82 if col != 'purple' or 'UDC driver' not in t else 82
yd_end = y - 82 + 64
# cable
cy = yd_end - 32
s.raw(f'<path d="M {hx+hw} {yh_end-32} C 600 {yh_end-32}, 620 {cy}, {dx} {cy}" stroke="#444" stroke-width="5" fill="none"/>')
s.text(560, yh_end + 30, 'USB cable', size=13, weight='bold', fill='#444', anchor='middle')
s.text(610, top + 260, 'An ssh packet goes DOWN the', size=12.5, fill='#555', anchor='middle', italic=True)
s.text(610, top + 278, 'PC\'s stack, across the cable,', size=12.5, fill='#555', anchor='middle', italic=True)
s.text(610, top + 296, 'and UP the board\'s stack.', size=12.5, fill='#555', anchor='middle', italic=True)
s.text(610, top + 316, '(Replies go the other way.)', size=12.5, fill='#555', anchor='middle', italic=True)
# --- bottom: three panels ---
by = yd_end + 40
s.box(20, by, 400, 250, 'teal', 'USB device classes (standard types)', [])
cls = [('CDC', 'Communications Device Class family'), ('NCM', 'network adapter, modern'),
       ('ECM', 'network adapter, older/simple'), ('RNDIS', 'Microsoft network protocol (old)'),
       ('ACM', 'serial port (ttyGS0 / ttyACM0 / COM)'), ('Mass storage', 'a disk / memory stick'),
       ('HID', 'keyboard, mouse')]
ry = by + 48
for a, b in cls:
    s.text(36, ry, a, size=12.5, weight='bold', mono=True)
    s.text(150, ry, b, size=12.5)
    ry += 26
s.box(440, by, 380, 250, 'purple', 'Two ways to build a gadget', [
    (('Legacy module', False, True), (' (fixed device, one command)', False, False)),
    (('   modprobe g_ncm', True, False), ('   g_mass_storage  g_serial', True, False)),
    '   options in /etc/modprobe.d/',
    (('   ✓ in our image: g_ncm, g_mass_storage', False, False)),
    '',
    (('configfs', False, True), (' (build it from parts)', False, False)),
    (('   mkdir /sys/kernel/config/usb_gadget/g1', True, False)),
    '   + write IDs, add functions (ncm, acm…),',
    '   link them into a config, bind to the UDC',
    '   ✗ not in our kernel yet (planned rebuild)',
])
s.box(840, by, 380, 250, 'green', 'Look at it on the board', [])
rows = [('lsmod | grep g_', 'gadget modules loaded'), ('ls /sys/class/udc/', 'musb-hdrc.0 = the port'),
        ('cat /sys/class/udc/*/state', 'configured / not attached'), ('ip addr show usb0', 'the gadget\'s network side'),
        ('dmesg | grep -i musb', 'controller messages')]
ry = by + 48
for cmd, desc in rows:
    s.text(856, ry, cmd, size=12, weight='bold', mono=True)
    s.text(868, ry + 16, '↳ ' + desc, size=11.5, fill='#2e7d32', italic=True)
    ry += 38
s.save(sys.argv[2])
