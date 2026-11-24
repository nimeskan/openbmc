import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C
W, H = 1240, 1030
s = Svg(W, H, 'Kernel, drivers and modules cheat sheet')
s.text(W/2, 34, 'Kernel, drivers and modules', size=24, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'How a program reaches the hardware, which parts are built in, and which are loadable modules. Examples from our BeagleBone.',
       size=14, fill='#555', anchor='middle')

# ---------- left: the stack ----------
L, R = 20, 790
def band(y, h, label, colour):
    f, st, t = C[colour]
    s.raw(f'<rect x="{L}" y="{y}" width="{R-L}" height="{h}" rx="12" fill="{f}" fill-opacity="0.45" stroke="{st}" stroke-width="1.5"/>')
    s.text(L + 12, y + 20, label, size=13, weight='bold', fill=t)

band(80, 236, 'USER SPACE  (programs; can\'t touch hardware directly)', 'green')
s.box(40, 110, 230, 74, 'green', 'Programs', [
    (('gpioset  bmcweb  ssh', True, False)),
    (('your bbb-led-standin', True, False)),
], center=True)
s.box(290, 110, 230, 74, 'green', 'Daemons', [
    'programs that run in the background',
    (('systemd-networkd  phosphor-…', True, False)),
], center=True)
s.box(540, 110, 230, 74, 'green', 'Commands you type', [
    (('modprobe  ip  busctl  cat', True, False)),
    'are programs too',
], center=True)
s.box(40, 206, 730, 64, 'teal', 'Libraries  (shared code in /usr/lib/*.so)', [
    (('libc.so.6 (glibc)   libgpiod.so.2   libsystemd.so.0   libstdc++.so.6   libi2c.so.0', True, False)),
], center=True)
for x in (155, 405, 655):
    s.arrow(x, 184, x, 204)
s.text(L + 12, 298, 'Runs as normal processes: a bug crashes one program, not the system.', size=12.5, fill='#1c5e2e', italic=True)

# syscall line
s.raw(f'<line x1="{L}" y1="330" x2="{R}" y2="330" stroke="#d14a4a" stroke-width="3" stroke-dasharray="10,6"/>')
s.rich(L + 12, 352, [('SYSTEM CALLS:  ', False, True), ('open() read() write() ioctl() socket()', True, False),
                      ('  — the only way into the kernel', False, False)], size=13)
s.arrow(730, 270, 730, 408)

band(380, 420, 'KERNEL SPACE  (one big program: zImage + loaded modules; full hardware access)', 'purple')
s.box(40, 410, 730, 74, 'purple', 'Interfaces the kernel offers to programs', [
    (('/dev/gpiochip0  /dev/i2c-2  /dev/ttyS0', True, False), ('  (device files)    ', False, False), ('/sys/…', True, False), ('  (sysfs)    network sockets', False, False)),
], center=True)
s.arrow(405, 484, 405, 506)
s.box(40, 508, 730, 98, 'purple', 'Subsystems  (generic: the same on every chip)', [
    (('gpiolib', True, True), ('     ', False, False), ('I2C core', True, True), ('     ', False, False), ('network stack', True, True), ('     ', False, False), ('USB gadget core', True, True), ('     ', False, False), ('hwmon', True, True)),
    (('LED class', True, True), (' (not in our kernel)     ', False, False), ('MTD/MMC block', True, True), ('     ', False, False), ('pin control', True, True)),
    'Each defines a standard "table of functions" that drivers fill in (e.g. struct gpio_chip).',
], center=True)
s.arrow(405, 606, 405, 628)
s.box(40, 630, 730, 112, 'purple', 'Drivers  (specific: know one chip\'s registers)', [
    (('gpio-omap', True, False), ('  ', False, False), ('i2c-omap', True, False), ('  ', False, False), ('cpsw', True, False), (' (Ethernet)  ', False, False), ('musb + musb_dsps', True, False), (' (USB)  ', False, False), ('tps65217', True, False), (' (PMIC)', False, False)),
    (('Built in (always there): ', False, True), ('all of the above', False, False)),
    (('Modules (loaded on demand): ', False, True), ('g_ncm.ko  u_ether.ko  libcomposite.ko  g_mass_storage.ko', True, False)),
    'A bug here can crash or hang the whole board.',
], center=True)
s.arrow(405, 742, 405, 822)
s.text(415, 782, 'reads/writes hardware registers (e.g. 0x4804C194)', size=12.5, fill='#555')

f, st, t = C['grey']
s.raw(f'<rect x="{L}" y="824" width="{R-L}" height="80" rx="12" fill="#ececec" stroke="#666" stroke-width="1.5"/>')
s.text(L + 12, 844, 'HARDWARE', size=13, weight='bold', fill='#333')
s.text(405, 870, 'AM335x processor blocks (GPIO banks, I2C controllers, USB, Ethernet MAC) + board chips (PMIC, EEPROM, LEDs)',
       size=12.5, anchor='middle')
s.text(405, 890, 'described to the kernel by the device tree: /boot/am335x-boneblack.dtb', size=12.5, anchor='middle', mono=True)

# ---------- right column ----------
x, w = 810, 410
y = 80
s.box(x, y, w, 154, 'grey', 'Three words', [
    (('Kernel', False, True), (': the core of Linux. Starts first (zImage),', False, False)),
    'owns the hardware, runs every program.',
    (('Driver', False, True), (': kernel code for one kind of hardware.', False, False)),
    (('Module', False, True), (': a driver (or other kernel code) kept in a', False, False)),
    (('separate ', False, False), ('.ko', True, True), (' file, plugged into the RUNNING kernel', False, False)),
    'when needed. Must match that exact kernel build.',
])
y += 166
s.box(x, y, w, 154, 'yellow', 'Built in, module, or missing?', [
    (('CONFIG_X=y', True, True), ('   inside zImage, always active', False, False)),
    (('CONFIG_X=m', True, True), ('   a .ko in /lib/modules, load it', False, False)),
    (('# CONFIG_X is not set', True, True), ('  absent: rebuild', False, False)),
    'Check on the board:',
    (('zcat /proc/config.gz | grep USB_G_NCM', True, False)),
    (('→ ', False, False), ('CONFIG_USB_G_NCM=m', True, False)),
])
y += 166
s.box(x, y, w, 212, 'blue', 'Loading a module:  modprobe g_ncm', [
    (('1. reads ', False, False), ('/lib/modules/$(uname -r)/modules.dep', True, False)),
    '   → g_ncm needs u_ether, libcomposite, configfs',
    (('2. reads options from ', False, False), ('/etc/modprobe.d/*.conf', True, False)),
    (('   e.g. ', False, False), ('options g_ncm dev_addr=02:bb:…', True, False)),
    '3. loads, in order:',
    (('   configfs → libcomposite → u_ether → g_ncm', True, False)),
    (('4. the module\'s init code runs (here: creates ', False, False), ('usb0', True, False), (')', False, False)),
    (('Undo: ', False, True), ('modprobe -r g_ncm', True, False)),
    (('At boot: a service runs it (our image has no ', False, False), ('modules-load', True, False), (')', False, False)),
])
y += 224
s.box(x, y, w, 186, 'purple', 'How a driver finds its hardware', [
    (('Device tree node:  ', False, False), ('compatible = "ti,omap4-gpio"', True, False)),
    (('Driver\'s match table: ', False, False), ('{ "ti,omap4-gpio", … }', True, False)),
    '      ↓ the kernel pairs them ("binding")',
    (('driver\'s ', False, False), ('probe()', True, True), (' runs: map registers, set up,', False, False)),
    'register with its subsystem',
    '      ↓',
    (('/dev/gpiochip0', True, False), (' and ', False, False), ('/sys/bus/gpio/…', True, False), (' appear', False, False)),
    (('See bindings: ', False, False), ('ls /sys/bus/platform/drivers/', True, False)),
])
y += 198
s.box(x, y, w, 176, 'green', 'Commands (on the board)')
rows = [('lsmod', 'loaded modules'), ('modprobe X', 'load X (+ what it needs)'), ('modprobe -r X', 'unload X'),
        ('modinfo X', 'description, parameters'), ('dmesg', 'kernel messages'), ('uname -r', 'running kernel version'),
        ('zcat /proc/config.gz', 'how the kernel was built')]
ry = y + 46
for cmd, desc in rows:
    s.text(x + 12, ry, cmd, size=12.5, weight='bold', mono=True)
    s.text(x + 200, ry, desc, size=12.5)
    ry += 18
s.save(sys.argv[2])
