import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg
W, H = 1240, 1240
s = Svg(W, H, 'Linux folders cheat sheet: what lives where (on our BeagleBone OpenBMC image)')
s.text(W/2, 34, 'Where things live in Linux', size=24, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'Our BeagleBone OpenBMC image. Colours tell you where a folder really is, and what survives a reboot or a re-flash.',
       size=14, fill='#555', anchor='middle')

# legend
lx, ly = 30, 80
legend = [('blue', 'Root partition: the image\'s own files'), ('green', 'Root partition: your additions & settings'),
          ('yellow', 'Other partitions'), ('orange', 'In RAM: empty after every reboot'), ('purple', 'Made by the kernel (not real files)')]
for col, lab in legend:
    from lib import C
    f, st, t = C[col]
    s.raw(f'<rect x="{lx}" y="{ly}" width="22" height="16" rx="3" fill="{f}" stroke="{st}" stroke-width="2"/>')
    s.text(lx + 30, ly + 13, lab, size=13)
    lx += 30 + len(lab) * 6.3 + 14

# ---------------- column 1: /usr (blue) ----------------
x, w = 20, 395
s.text(x, 128, 'THE IMAGE\'S FILES', size=13, weight='bold', fill='#4a6fd1')
s.box(x, 138, w, 92, 'grey', '/   (the root folder)', [
    'Everything hangs off "/". Partition 2 of the eMMC',
    '(/dev/mmcblk1p2, ext4) is mounted here.',
    (('Shortcuts: ', False, False), ('/bin /sbin /lib', True, False), (' → ', False, False), ('/usr/…', True, False)),
], title_mono=True)
y = 242
s.box(x, y, w, 96, 'blue', '/usr/bin   /usr/sbin', [
    'Programs (commands) you can run.',
    (('e.g. ', False, False), ('gpioset  busctl  ip  systemctl', True, False)),
    (('sbin = admin tools, e.g. ', False, False), ('modprobe', True, False)),
], title_mono=True)
y += 108
s.box(x, y, w, 96, 'blue', '/usr/lib', [
    (('Shared libraries ', False, False), ('*.so', True, False), (': code programs load', False, False)),
    (('e.g. ', False, False), ('libc.so.6  libgpiod.so.2  libsystemd.so.0', True, False)),
    (('(', False, False), ('/lib', True, False), (' is a shortcut to here)', False, False)),
], title_mono=True)
y += 108
s.box(x, y, w, 112, 'blue', '/usr/lib/systemd/system', [
    'The image\'s systemd unit files',
    (('e.g. ', False, False), ('bmcweb.service  dropbear.socket', True, False)),
    (('Don\'t edit: override in ', False, False), ('/etc/systemd/system', True, True)),
    (('Network defaults: ', False, False), ('/usr/lib/systemd/network', True, False)),
], title_mono=True)
y += 124
s.box(x, y, w, 96, 'blue', '/usr/libexec', [
    'Helper programs that services start (not for',
    (('typing). OpenBMC daemons: ', False, False), ('phosphor-led-manager/', True, False)),
    (('phosphor-ledmanager', True, False), (', ', False, False), ('phosphor-objmgr/', True, False), ('…', False, False)),
], title_mono=True)
y += 108
s.box(x, y, w, 96, 'blue', '/usr/share', [
    'Read-only data that comes with programs',
    (('D-Bus policies: ', False, False), ('/usr/share/dbus-1/system.d', True, False)),
    (('Default configs, e.g. ', False, False), ('/usr/share/phosphor-…', True, False)),
], title_mono=True)
y += 108
s.box(x, y, w, 112, 'blue', '/lib/modules/<kernel version>', [
    (('Kernel modules ', False, False), ('*.ko', True, True), (' (drivers loaded on demand)', False, False)),
    (('e.g. ', False, False), ('…/drivers/usb/gadget/legacy/g_ncm.ko', True, False)),
    (('modules.dep', True, False), (': what needs what (read by modprobe)', False, False)),
    (('Version: ', False, False), ('uname -r', True, False)),
], title_mono=True)
y_end1 = y + 112

# ---------------- column 2: /etc etc (green) ----------------
x, w = 432, 395
s.text(x, 128, 'YOUR ADDITIONS & SETTINGS', size=13, weight='bold', fill='#2e9a4b')
y = 138
s.box(x, y, w, 236, 'green', '/etc   (settings)', [
    'System-wide configuration. Plain text files.',
    'Files here override the image\'s defaults.',
    (('systemd/system/', True, True), ('   your units + overrides', False, False)),
    (('   …/multi-user.target.wants/', True, False), ('  = "enabled"', False, False)),
    (('systemd/network/', True, True), ('  network files (*.network)', False, False)),
    (('modprobe.d/', True, True), ('       module options', False, False)),
    (('phosphor-led-manager/', True, True), (' LED group config', False, False)),
    (('fstab', True, True), ('  what to mount where, at boot', False, False)),
    (('hostname  passwd  shadow  dropbear/', True, False)),
    (('dbus-1/system.d/', True, False), ('  extra D-Bus policies', False, False)),
], title_mono=False)
y += 248
s.box(x, y, w, 92, 'green', '/usr/local/bin', [
    'Programs YOU add (not from the image)',
    (('e.g. ', False, False), ('bbb-led-standin', True, False)),
    'Kept apart so you always know what\'s yours.',
], title_mono=True)
y += 104
s.box(x, y, w, 76, 'green', '/home/root   ( ~ )', [
    (('root\'s home folder. ', False, False), ('scp … root@board:', True, False), (' lands here.', False, False)),
    (('(On a PC: ', False, False), ('/home/<you>', True, False), (')', False, False)),
], title_mono=True)
y += 88
s.box(x, y, w, 92, 'green', '/var/lib   /var/log', [
    (('/var', True, False), (' = data that changes while running', False, False)),
    (('lib/', True, True), (': programs\' saved state (survives reboot)', False, False)),
    (('log/', True, True), (': log files. Read logs with ', False, False), ('journalctl', True, False)),
], title_mono=True)
y += 104
s.box(x, y, w, 128, 'grey', 'What survives what?', [
    'Reboot: everything on the eMMC partitions survives;',
    'RAM folders (orange) are emptied.',
    (('Re-flash: ', False, True), ('the WHOLE root partition is replaced,', False, False)),
    (('/etc', True, False), (' and ', False, False), ('/usr/local', True, False), (' too. Keep copies on your PC,', False, False)),
    (('or put lasting data on ', False, False), ('/data', True, True), (' (partition 3).', False, False)),
])

# ---------------- column 3: kernel / RAM / partitions ----------------
x, w = 844, 376
s.text(x, 128, 'NOT ORDINARY FILES', size=13, weight='bold', fill='#8a4ad1')
y = 138
s.box(x, y, w, 76, 'purple', '/dev   (device files)', [
    'Special files that talk to drivers:',
    (('gpiochip0  i2c-2  ttyS0  mmcblk1p2', True, False)),
], title_mono=False)
y += 88
s.box(x, y, w, 76, 'purple', '/proc', [
    (('Processes and kernel info. ', False, False), ('/proc/config.gz', True, False)),
    (('(kernel build options), ', False, False), ('/proc/partitions', True, False)),
], title_mono=True)
y += 88
s.box(x, y, w, 170, 'purple', '/sys   (sysfs)', [
    'Every device and driver, as folders + files',
    (('class/', True, True), (' by kind: ', False, False), ('net/  udc/  leds/  hwmon/', True, False)),
    (('bus/', True, True), (' by bus: ', False, False), ('gpio/  i2c/  platform/drivers/', True, False)),
    (('firmware/devicetree/base/', True, True), (' the device tree', False, False)),
    (('kernel/config/', True, True), (' configfs: you CREATE objects', False, False)),
    (('kernel/debug/', True, True), (' debugfs: developer info', False, False)),
    (('cat', True, False), (' to read, ', False, False), ('echo … >', True, False), (' to set', False, False)),
], title_mono=False)
s.text(x, y + 196, 'IN RAM', size=13, weight='bold', fill='#d14a4a')
y += 206
s.box(x, y, w, 112, 'orange', '/run   /tmp   /var/volatile', [
    (('/run', True, True), (': info about the running system', False, False)),
    (('(e.g. ', False, False), ('/run/systemd/', True, False), (', pid files)', False, False)),
    (('/tmp', True, True), (', ', False, False), ('/var/tmp', True, False), (': scratch files', False, False)),
    'Fast, but gone after every reboot.',
], title_mono=True)
s.text(x, y + 138, 'OTHER PARTITIONS (eMMC /dev/mmcblk1)', size=13, weight='bold', fill='#d48a00')
y += 148
s.box(x, y, w, 112, 'yellow', '/boot   (partition 1, FAT)', [
    'What U-Boot loads to start Linux:',
    (('MLO  u-boot.img  zImage', True, False)),
    (('am335x-boneblack.dtb', True, False)),
    (('extlinux/extlinux.conf', True, False), (' (boot menu)', False, False)),
], title_mono=False)
y += 124
s.box(x, y, w, 76, 'yellow', '/data   (partition 3, optional)', [
    'Your own space; a re-flash of the image',
    'doesn\'t touch it.',
], title_mono=False, dash=True)
y += 88
s.box(x, y, w, 60, 'grey', '/mnt   /media', [
    'Empty mount points for disks you attach.',
], title_mono=True)

# ---------------- bottom: rules of thumb + eMMC strip ----------------
by = 1000
s.box(20, by, 805, 222, 'grey', 'Rules of thumb', [
    (('1. ', False, True), ('Image = ', False, False), ('/usr', True, True), ('.  Yours = ', False, False), ('/etc', True, True), ('  ', False, False), ('/usr/local', True, True), ('  ', False, False), ('/home/root', True, True), ('.', False, False)),
    (('2. ', False, True), ('Override, don\'t edit: same file name in ', False, False), ('/etc/systemd/system/', True, False), (' wins over', False, False)),
    (('    ', False, False), ('/usr/lib/systemd/system/', True, False), (' (also for ', False, False), ('network/', True, False), (' and other config folders).', False, False)),
    (('3. ', False, True), ('Programs: ', False, False), ('bin', True, False), ('. Libraries: ', False, False), ('lib', True, False), ('. Settings: ', False, False), ('etc', True, False), ('. Changing data: ', False, False), ('var', True, False), ('. Shared data: ', False, False), ('share', True, False), ('.', False, False)),
    (('4. ', False, True), ('/proc', True, False), (' ', False, False), ('/sys', True, False), (' ', False, False), ('/dev', True, False), (' are the kernel talking: not stored anywhere, rebuilt at every boot.', False, False)),
    (('5. ', False, True), ('Find where something is: ', False, False), ('which gpioset', True, False), ('   ', False, False), ('systemctl cat bmcweb', True, False), ('   ', False, False), ('df -h', True, False), ('   ', False, False), ('mount', True, False)),
    (('6. ', False, True), ('Same layout on your Ubuntu PC (plus ', False, False), ('/usr/include', True, False), (' for C headers, ', False, False), ('/opt', True, False), (' for big apps).', False, False)),
], line_gap=24, line_size=13.5)
# eMMC strip
ex, ey, ew = 844, 1000, 376
s.text(ex, ey + 18, 'The eMMC (/dev/mmcblk1)', size=15, weight='bold', fill='#333')
parts = [('p1', '/boot', 0.12, 'yellow'), ('p2', '/  (root)', 0.32, 'blue'), ('p3', '/data', 0.56, 'yellow')]
px = ex
from lib import C
for name, mnt, frac, col in parts:
    pw = ew * frac
    f, st, t = C[col]
    dash = ' stroke-dasharray="6,4"' if name == 'p3' else ''
    s.raw(f'<rect x="{px}" y="{ey+32}" width="{pw}" height="64" fill="{f}" stroke="{st}" stroke-width="2"{dash}/>')
    s.text(px + pw/2, ey + 58, name, size=13, weight='bold', fill=t, anchor='middle', mono=True)
    s.text(px + pw/2, ey + 80, mnt, size=12, anchor='middle', mono=True)
    px += pw
s.text(ex, ey + 122, 'p1 32 MB FAT, p2 141 MB ext4 (the image),', size=12.5)
s.text(ex, ey + 140, 'p3 = the optional 3.4 GB data partition.', size=12.5)
s.text(ex, ey + 166, 'The SD card is /dev/mmcblk0 (same layout).', size=12.5)
s.text(ex, ey + 192, 'See the partitions with:', size=12.5)
s.rich(ex, ey + 210, [('cat /proc/partitions', True, False), ('   and   ', False, False), ('df -h', True, False)], size=12.5)
s.save(sys.argv[2])
