import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C
W, H = 1240, 1160
s = Svg(W, H, 'systemd cheat sheet: services, units, daemons')
s.text(W/2, 34, 'systemd: units, services and daemons', size=24, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'How programs get started at boot and kept running, and how you add your own. Examples from our BeagleBone.',
       size=14, fill='#555', anchor='middle')

# ---- boot chain (top row) ----
y0 = 84
steps = [('Power on', 'ROM → MLO → U-Boot', 'yellow'), ('Linux kernel', 'zImage + device tree', 'purple'),
         ('systemd', 'the first program: PID 1', 'blue'), ('Units started', 'in dependency order', 'green')]
x = 20
for i, (t, sub, col) in enumerate(steps):
    s.box(x, y0, 276, 62, col, t, [sub], center=True)
    if i < 3:
        s.arrow(x + 276, y0 + 31, x + 306, y0 + 31)
    x += 308

# ---- left column: where units come from + boot targets ----
x, w = 20, 400
y = 166
s.text(x, y + 6, 'WHERE UNIT FILES LIVE', size=13, weight='bold', fill='#4a6fd1')
s.box(x, y + 16, w, 78, 'blue', '/usr/lib/systemd/system/', [
    'The image\'s units (bmcweb.service, …).',
    'Replaced by a re-flash. Don\'t edit.',
], title_mono=True)
s.box(x, y + 106, w, 96, 'green', '/etc/systemd/system/', [
    'YOUR units, and overrides: a file here with',
    'the same name replaces the image\'s one.',
    (('Drop-ins: ', False, True), ('X.service.d/*.conf', True, False), (' change only some lines', False, False)),
], title_mono=True)
s.box(x, y + 214, w, 60, 'orange', '/run/systemd/  (RAM)', [
    'Generated at run time. Ignore.',
], title_mono=True)
s.rich(x, y + 300, [('See the file systemd actually uses: ', False, False), ('systemctl cat bmcweb', True, True)], size=13)

y = 490
s.text(x, y, 'BOOT = REACHING TARGETS', size=13, weight='bold', fill='#2e9a4b')
tg = [('sysinit.target', 'mount file systems, udev, …'), ('sockets.target', 'listen: dropbear.socket (22), bmcweb.socket (443)'),
      ('network.target', 'systemd-networkd up'), ('multi-user.target', '"system is up": most services, incl. yours'),
      ('(after multi-user)', 'obmc-led-group-start@bmc_booted …')]
ty = y + 12
for i, (t, d) in enumerate(tg):
    col = 'green' if i < 4 else 'grey'
    f, st, tc = C[col]
    s.raw(f'<rect x="{x}" y="{ty}" width="{w}" height="42" rx="8" fill="{f}" stroke="{st}" stroke-width="2"/>')
    s.text(x + 12, ty + 19, t, size=13, weight='bold', fill=tc, mono=True)
    s.text(x + 12, ty + 37, d, size=12)
    if i < 4:
        s.arrow(x + w/2, ty + 42, x + w/2, ty + 57)
    ty += 58
s.text(x, ty + 12, 'A target is just a named milestone that groups units.', size=12.5, italic=True, fill='#555')

# ---- middle column: unit types + daemon ----
x, w = 440, 380
y = 166
s.text(x, y + 6, 'KINDS OF UNIT  (file name ending)', size=13, weight='bold', fill='#8a4ad1')
s.box(x, y + 16, w, 172, 'purple', '.service  — run a program', [
    (('Type=simple', True, True), (' / ', False, False), ('Type=dbus', True, True), (': a long-running', False, False)),
    (('daemon', False, True), ('. systemd watches it, restarts it', False, False)),
    (('if ', False, False), ('Restart=on-failure', True, False), ('. e.g. bmcweb, our stand-in', False, False)),
    (('Type=oneshot', True, True), (': run a command, then done.', False, False)),
    (('With ', False, False), ('RemainAfterExit=yes', True, False), (' it stays "active"', False, False)),
    (('so ', False, False), ('stop', True, False), (' runs ExecStop. e.g. usb-ncm-gadget', False, False)),
], title_mono=False)
s.box(x, y + 200, w, 116, 'purple', '.socket  — listen, start on demand', [
    'systemd opens the port itself; the service',
    'starts when the first connection arrives.',
    (('dropbear.socket', True, False), (' → ', False, False), ('dropbear@.service', True, False), (' (SSH)', False, False)),
    (('bmcweb.socket', True, False), (' → ', False, False), ('bmcweb.service', True, False), (' (HTTPS)', False, False)),
])
s.box(x, y + 328, w, 80, 'purple', '.target  — a milestone / group', [
    (('multi-user.target', True, False), (' = "fully booted"', False, False)),
    'Units say they belong to one (WantedBy=).',
])
s.box(x, y + 420, w, 62, 'grey', 'Others you\'ll see', [
    (('.mount  .timer  .path  .device  .slice', True, False)),
])
s.box(x, y + 494, w, 130, 'teal', 'Daemon  (a word, not a unit type)', [
    'A program that runs in the background,',
    'waiting to do work, for as long as the system',
    'runs: bmcweb, systemd-networkd, avahi-daemon,',
    'phosphor-ledmanager. Usually started by a',
    '.service unit. Its output goes to the journal.',
])
s.box(x, y + 636, w, 140, 'yellow', 'start vs enable', [
    (('systemctl start X', True, True), ('  run it NOW (until reboot)', False, False)),
    (('systemctl enable X', True, True), ('  start it at every BOOT:', False, False)),
    (('   makes a link in ', False, False), ('…/multi-user.target.wants/', True, False)),
    (('systemctl enable --now X', True, True), ('  both', False, False)),
    (('disable', True, True), (' removes the link; ', False, False), ('stop', True, True), (' stops it now', False, False)),
])

# ---- right column: anatomy of a unit file ----
x, w = 840, 380
y = 166
s.text(x, y + 6, 'ANATOMY OF A UNIT FILE', size=13, weight='bold', fill='#d48a00')
f, st, tc = C['grey']
s.raw(f'<rect x="{x}" y="{y+16}" width="{w}" height="458" rx="10" fill="#fbfbfb" stroke="#888" stroke-width="2"/>')
code = [
    ('[Unit]', 'section: description + ordering', True),
    ('Description=BeagleBone LED stand-in', 'shown in status and logs', False),
    ('Wants=…ObjectMapper.service', 'also start that one', False),
    ('After=…ObjectMapper.service', 'but only after it', False),
    ('Before=…GroupManager.service', 'and before this one', False),
    ('', '', False),
    ('[Service]', 'section: how to run it', True),
    ('Type=dbus', '"started" = has claimed BusName', False),
    ('BusName=xyz.openbmc_project.LED.GpioStandIn', '', False),
    ('ExecStart=/usr/local/bin/bbb-led-standin', 'the program', False),
    ('ExecStartPost=/usr/bin/mapper wait …', 'run after it starts', False),
    ('Restart=on-failure', 'restart it if it crashes', False),
    ('', '', False),
    ('[Install]', 'section: used by enable', True),
    ('WantedBy=multi-user.target', 'enable → start at boot', False),
]
cy = y + 40
for line, note, hdr in code:
    if line:
        s.text(x + 12, cy, line, size=11.5, mono=True, weight='bold' if hdr else 'normal', fill='#7a4d00' if hdr else '#222')
    if note:
        s.text(x + 24, cy + 14, '↳ ' + note, size=11.5, fill='#2e7d32', italic=True)
        cy += 14
    cy += 17
s.text(x + 12, y + 494, 'Wants/Requires = "start together".', size=12.5)
s.text(x + 12, y + 512, 'After/Before = "in this order". They\'re separate!', size=12.5)
s.text(x + 12, y + 530, 'Change a unit file? Run  systemctl daemon-reload', size=12.5)

s.box(x, y + 556, w, 262, 'green', 'Everyday commands', [])
rows = [('systemctl status X', 'running? + last log lines'), ('systemctl start|stop|restart X', ''),
        ('systemctl enable|disable X', ''), ('systemctl daemon-reload', 'after editing units'),
        ('systemctl list-units --type=service', ''), ('systemctl cat X', 'the unit file in use'),
        ('journalctl -u X -b', 'X\'s log, this boot'), ('journalctl -f', 'follow all logs live')]
ry = y + 600
for cmd, desc in rows:
    s.text(x + 12, ry, cmd, size=12, weight='bold', mono=True)
    if desc:
        s.text(x + 24, ry + 15, '↳ ' + desc, size=11.5, fill='#2e7d32', italic=True)
        ry += 15
    ry += 19

# ---- bottom strip: example ----
by = 1000
s.box(20, by, 1200, 140, 'grey', 'Example: how our LED stand-in starts at every boot', [
    (('1. ', False, True), ('systemctl enable bbb-led-standin', True, False), (' created ', False, False), ('/etc/systemd/system/multi-user.target.wants/bbb-led-standin.service', True, False), (' (a link).', False, False)),
    (('2. ', False, True), ('At boot, systemd heads for multi-user.target, finds that link, and starts the unit after the object mapper (', False, False), ('After=', True, False), (').', False, False)),
    (('3. ', False, True), ('Type=dbus', True, False), (': it counts as started once the program claims its D-Bus name; then ', False, False), ('ExecStartPost', True, False), (' waits for the mapper.', False, False)),
    (('4. ', False, True), ('Only then do units ordered after it run (', False, False), ('Before=', True, False), (' GroupManager, bmc_booted). Output → ', False, False), ('journalctl -u bbb-led-standin', True, False)),
], line_gap=22)
s.save(sys.argv[2])
