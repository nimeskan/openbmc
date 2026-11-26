"""Generate the identify/heartbeat LED diagrams.
Usage: python3 leds.py <dir with lib.py> <out dir>"""
import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C
OUT = sys.argv[2]

def legend(s, y, items):
    lx = 20
    for col, lab in items:
        f, st, t = C[col]
        dash = ' stroke-dasharray="5,3"' if col == 'grey' and 'idle' in lab else ''
        s.raw(f'<rect x="{lx}" y="{y}" width="22" height="16" rx="3" fill="{f}" stroke="{st}" stroke-width="2"{dash}/>')
        s.text(lx + 30, y + 13, lab, size=13)
        lx += 30 + len(lab) * 6.9 + 24

def plug(s, x1, y1, x2, y2, label, side='right', colour='#555', dash=False):
    """arrow with a small label box ('the plug')"""
    s.arrow(x1, y1, x2, y2, colour=colour, dash=dash)
    lx = (x1 + x2) / 2 + (8 if side == 'right' else -8)
    ly = (y1 + y2) / 2 + 4
    s.text(lx, ly, label, size=11.5, fill='#7a4d00', anchor='start' if side == 'right' else 'end', mono=True)

# =====================================================================
# 1. Architecture tree
# =====================================================================
W, H = 1500, 1236
s = Svg(W, H, 'Identify and heartbeat LEDs: architecture')
s.text(W/2, 34, 'Identify and heartbeat LEDs: every layer and how they plug together', size=23, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'Our BeagleBone with the LED stand-in (C++ or Rust version). Labels on arrows (orange) are the exact "plugs": D-Bus names, paths, properties, files.',
       size=13.5, fill='#555', anchor='middle')
legend(s, 74, [('teal', 'outside the board'), ('blue', 'standard OpenBMC / Linux (in the image)'),
               ('green', 'added by us (stand-in, config, unit)'), ('purple', 'Linux kernel'), ('grey', 'hardware')])

MX = 20; MW = 1010   # main column
# --- clients ---
y = 108
s.text(MX, y + 4, 'WHO ASKS FOR AN LED', size=13, weight='bold', fill='#2a9d9d')
s.box(MX, y + 12, 240, 70, 'teal', 'Web UI (browser on PC)', ['Overview → "System identify LED"'], center=True)
s.box(MX + 256, y + 12, 240, 70, 'teal', 'Any Redfish client', ['curl, fleet tools, scripts'], center=True)
s.box(MX + 512, y + 12, 250, 70, 'blue', 'obmc-led-group-start@', ['bmc_booted.service (at boot)'], center=True)
s.box(MX + 778, y + 12, 232, 70, 'green', 'You, by hand (testing)', [('busctl set-property …', True, False)], center=True)

# --- bmcweb ---
y = 240
s.box(MX, y, 496, 92, 'blue', 'bmcweb  (Redfish + web server)', [
    'translates Redfish into D-Bus. For identify it sets the group',
    (('enclosure_identify_blink', True, False), (' (falls back to ', False, False), ('enclosure_identify', True, False), (')', False, False)),
    (('started by ', False, False), ('bmcweb.socket', True, False), (' on port 443', False, False)),
], center=True)
s.arrow(MX + 120, 190, MX + 120, 238)
s.text(MX + 128, 207, 'HTTPS :443  PATCH …/Systems/system', size=11.5, fill='#7a4d00', mono=True)
s.text(MX + 128, 223, '{"LocationIndicatorActive": true}', size=11.5, fill='#7a4d00', mono=True)
s.arrow(MX + 376, 190, MX + 376, 238)

# --- D-Bus bar ---
y = 370
s.raw(f'<rect x="{MX}" y="{y}" width="{MW}" height="38" rx="8" fill="#e8f0fe" stroke="#4a6fd1" stroke-width="2"/>')
s.rich(MX + MW/2, y + 24, [('System D-Bus (dbus-broker)', False, True), ('   — every arrow below this line travels over it as a message', False, False)], size=13.5, anchor='middle')
plug(s, MX + 248, 332, MX + 248, 368, 'Set …/enclosure_identify_blink  Asserted=true')
s.arrow(MX + 637, 190, MX + 637, 368)
s.text(MX + 645, 300, 'Set …/groups/bmc_booted', size=11.5, fill='#7a4d00', mono=True)
s.text(MX + 645, 316, 'Asserted = true', size=11.5, fill='#7a4d00', mono=True)
s.arrow(MX + 894, 190, MX + 894, 368)
s.text(MX + 902, 300, 'set a group,', size=11.5, fill='#7a4d00', mono=True)
s.text(MX + 902, 316, 'or an LED directly', size=11.5, fill='#7a4d00', mono=True)

# --- GroupManager + config + mapper ---
s.arrow(MX + 300, 408, MX + 300, 444)
s.text(MX + 308, 430, 'delivered to the owner of xyz.openbmc_project.LED.GroupManager', size=11.5, fill='#7a4d00', mono=True)
y = 446
s.box(MX, y, 600, 230, 'blue', 'phosphor-ledmanager   bus name: xyz.openbmc_project.LED.GroupManager', [], title_size=14)
s.text(MX + 14, y + 46, 'Publishes one object per LED GROUP (interface xyz.openbmc_project.Led.Group, property Asserted: b):', size=12.5)
gy = y + 58
for g, what in [('bmc_booted', '→ beaglebone_heartbeat_green  Blink  10 % of 1000 ms'),
                ('enclosure_identify_blink', '→ beaglebone_usr3_green  Blink  50 % of 1000 ms'),
                ('enclosure_identify', '→ beaglebone_usr3_green  On')]:
    s.raw(f'<rect x="{MX+14}" y="{gy}" width="572" height="40" rx="6" fill="#ffffff" stroke="#4a6fd1" stroke-width="1.2"/>')
    s.text(MX + 24, gy + 17, f'/xyz/openbmc_project/led/groups/{g}', size=12, mono=True, weight='bold')
    s.text(MX + 34, gy + 33, what, size=12, mono=True)
    gy += 46
s.text(MX + 14, gy + 14, 'When a group\'s Asserted changes: work out each member LED\'s new state', size=12.5)
s.text(MX + 14, gy + 30, '(Priority: Blink wins), find the LED\'s owner via the mapper, set its properties.', size=12.5)

s.box(MX + 620, y, 390, 104, 'green', '/etc/phosphor-led-manager/', [
    (('led-group-config.json', True, True)),
    'which LEDs are in which group, with action,',
    'period, duty and priority. Read once, at start.',
], title_mono=True)
plug(s, MX + 618, y + 52, MX + 602, y + 52, '', side='left')
s.box(MX + 620, y + 118, 390, 112, 'blue', 'Object mapper (phosphor-objmgr)', [
    (('xyz.openbmc_project.ObjectMapper', True, False)),
    'directory of who serves which object.',
    (('GetObject(path, [interface]) → bus name', True, False)),
    (('e.g. who serves …/beaglebone_usr3_green?', True, False)),
])
s.arrow(MX + 602, y + 186, MX + 618, y + 186)
s.arrow(MX + 618, y + 200, MX + 602, y + 200)

# --- stand-in ---
y = 730
plug(s, MX + 300, 676, MX + 300, y - 2, 'Set DutyOn (y), Period (q), then State (s) on …/led/physical/<name>')
s.box(MX, y, 760, 238, 'green', 'LED stand-in   bus name: xyz.openbmc_project.LED.GpioStandIn', [], title_size=14)
s.text(MX + 14, y + 44, '/usr/local/bin/bbb-led-standin (C++: sd-bus, libgpiod)  or  …-rs (Rust: zbus, gpiocdev)', size=12, mono=True)
s.text(MX + 14, y + 62, 'Publishes one object per PHYSICAL LED (interface xyz.openbmc_project.Led.Physical), and holds each GPIO line:', size=12.5)
py = y + 72
for name, line, use in [('beaglebone_heartbeat_green', '[usr0 led]', 'bmc_booted'),
                        ('beaglebone_mmc0_green', '[usr1 led]', 'unused'),
                        ('beaglebone_usr2_green', '[usr2 led]', 'unused'),
                        ('beaglebone_usr3_green', '[usr3 led]', 'identify')]:
    s.raw(f'<rect x="{MX+14}" y="{py}" width="732" height="30" rx="6" fill="#ffffff" stroke="#2e9a4b" stroke-width="1.2"/>')
    s.text(MX + 24, py + 20, f'/xyz/openbmc_project/led/physical/{name}', size=12, mono=True, weight='bold')
    s.text(MX + 470, py + 20, f'→ line {line}', size=12, mono=True)
    s.text(MX + 620, py + 20, use, size=12, italic=True, fill='#555')
    py += 34
s.text(MX + 14, py + 14, 'Properties: State "…Physical.Action.Off/On/Blink" (s), DutyOn % (y), Period ms (q), Color (s, read-only)', size=12)
s.box(MX + 780, y, 230, 238, 'grey', 'phosphor-led-sysfs', [
    (('xyz.openbmc_project.', True, False)),
    (('  LED.Controller', True, False)),
    'The STANDARD bottom layer:',
    'publishes the same objects',
    'from /sys/class/leds.',
    (('Idle today: ', False, True), ('our kernel', False, False)),
    'has no LED driver. After the',
    'rebuild it replaces the',
    'stand-in, same object names.',
], dash=True, title_size=14)

# --- kernel ---
y = 1006
plug(s, MX + 380, 968, MX + 380, y - 2, 'ioctl on held line handles (/dev/gpiochip0): set value 1 / 0')
s.box(MX, y, 1010, 92, 'purple', 'Linux kernel', [
    (('/dev/gpiochip0', True, False), ('  →  gpiolib-cdev  →  gpiolib core  →  ', False, False), ('gpio-omap', True, False), (' driver  (lines owned by the stand-in: ', False, False), ('gpioinfo', True, False), (' shows it)', False, False)),
    (('/sys/class/leds', True, False), (' + leds-gpio driver: NOT in our kernel (CONFIG_LEDS_CLASS not set) — the reason for the stand-in', False, False)),
], center=True)
# --- hardware ---
y = 1134
s.arrow(MX + 505, 1098, MX + 505, y - 2)
s.text(MX + 515, 1120, 'DATAOUT 0x4804C13C, bits 21–24', size=11.5, fill='#7a4d00', mono=True)
s.box(MX, y, 1010, 80, 'grey', None, [])
lx = MX + 20
for led, line, role, col in [('USR0', 'GPIO1_21', '"heartbeat": BMC booted', '#2e9a4b'), ('USR1', 'GPIO1_22', 'unused', '#999'),
                             ('USR2', 'GPIO1_23', 'unused', '#999'), ('USR3', 'GPIO1_24', 'identify', '#2e9a4b')]:
    s.raw(f'<circle cx="{lx+14}" cy="{y+28}" r="10" fill="{col}" stroke="#333" stroke-width="1.5"/>')
    s.text(lx + 32, y + 26, f'{led}  ({line})', size=13, weight='bold')
    s.text(lx + 32, y + 46, role, size=12.5, italic=True, fill='#555')
    lx += 248
s.text(MX + 20, y + 70, 'The four blue user LEDs next to the Ethernet socket (drawn here by role)', size=12, fill='#555')

# ---- right column: systemd tree + files tree ----
RX, RW = 1050, 430
y = 108
s.text(RX, y + 4, 'WHO STARTS WHAT (systemd, at boot)', size=13, weight='bold', fill='#4a6fd1')
s.raw(f'<rect x="{RX}" y="{y+12}" width="{RW}" height="560" rx="10" fill="#fbfbfb" stroke="#888" stroke-width="2"/>')
tree = [
    (0, 'multi-user.target  (wants:)', 'blue', True),
    (1, 'dbus-broker.service', 'blue', False),
    (1, 'xyz.openbmc_project.ObjectMapper.service', 'blue', False),
    (1, 'bbb-led-standin.service', 'green', True),
    (2, 'Type=dbus: ready when it owns its bus name', None, False),
    (2, 'After=…ObjectMapper  ·  ExecStartPost=', None, False),
    (2, '  mapper wait …/beaglebone_usr3_green', None, False),
    (2, 'Before=…GroupManager, …bmc_booted', None, False),
    (1, 'phosphor-ledcontroller.service (sysfs, idle)', 'grey', False),
    (1, 'xyz.openbmc_project.LED.GroupManager.service', 'blue', True),
    (2, 'reads led-group-config.json at start', None, False),
    (1, 'bmcweb.socket  → bmcweb.service', 'blue', False),
    (0, 'after multi-user.target:', 'blue', True),
    (1, 'obmc-led-group-start@bmc_booted.service', 'blue', True),
    (2, 'busctl set-property …LED.GroupManager', None, False),
    (2, '  /xyz/openbmc_project/led/groups/bmc_booted', None, False),
    (2, '  xyz.openbmc_project.Led.Group Asserted b true', None, False),
]
ty = y + 38
for depth, label, col, bold in tree:
    x = RX + 16 + depth * 22
    if depth > 0:
        s.line(x - 14, ty - 12, x - 14, ty - 4, colour='#aaa', width=1.5)
        s.line(x - 14, ty - 4, x - 4, ty - 4, colour='#aaa', width=1.5)
    colour = C[col][2] if col else '#555'
    s.text(x, ty, label, size=12 if col else 11.5, mono=True, weight='bold' if bold else 'normal', fill=colour, italic=not col)
    ty += 24 if col else 19
s.text(RX + 16, ty + 10, 'Order matters: the stand-in must be ready and', size=12, fill='#555', italic=True)
s.text(RX + 16, ty + 27, 'known to the mapper before bmc_booted is asserted.', size=12, fill='#555', italic=True)

y = 700
s.text(RX, y + 4, 'FILES WE ADDED ON THE BOARD', size=13, weight='bold', fill='#2e9a4b')
s.raw(f'<rect x="{RX}" y="{y+12}" width="{RW}" height="300" rx="10" fill="#fbfbfb" stroke="#888" stroke-width="2"/>')
files = [
    (0, '/usr/local/bin/', True),
    (1, 'bbb-led-standin        (the program)', False),
    (0, '/etc/systemd/system/', True),
    (1, 'bbb-led-standin.service   (unit)', False),
    (1, 'multi-user.target.wants/', False),
    (2, 'bbb-led-standin.service → link', False),
    (2, '(made by systemctl enable)', False),
    (0, '/etc/phosphor-led-manager/', True),
    (1, 'led-group-config.json  (groups)', False),
]
ty = y + 40
for depth, label, bold in files:
    x = RX + 16 + depth * 22
    if depth > 0:
        s.line(x - 14, ty - 12, x - 14, ty - 4, colour='#aaa', width=1.5)
        s.line(x - 14, ty - 4, x - 4, ty - 4, colour='#aaa', width=1.5)
    s.text(x, ty, label, size=12, mono=True, weight='bold' if bold else 'normal', fill='#1c5e2e' if bold else '#333')
    ty += 22
s.text(RX + 16, ty + 10, 'Everything else is the standard image.', size=12, fill='#555', italic=True)
s.text(RX + 16, ty + 27, 'Rust version: same, with the -rs names.', size=12, fill='#555', italic=True)
s.text(RX + 16, ty + 44, 'Remove: section 11 of the C++ guide.', size=12, fill='#555', italic=True)

y = 1030
s.box(RX, y, RW, 184, 'grey', 'After the image rebuild', [
    'Kernel gets the LED driver → /sys/class/leds',
    'phosphor-led-sysfs publishes the SAME objects',
    '(beaglebone_usr3_green …) under its own bus name',
    '→ delete the stand-in; the mapper now answers',
    '"xyz.openbmc_project.LED.Controller".',
    'JSON config, groups, bmcweb: unchanged.',
    'Optional: let the kernel heartbeat own USR0.',
], line_gap=19)
s.save(f'{OUT}/leds-architecture.svg')

# =====================================================================
# 2. Sequences
# =====================================================================
def halo(s, x, y, txt, size, weight, fill, mono):
    from lib import esc, MONO
    fam = f' font-family="{MONO}"' if mono else ''
    s.raw(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}"{fam} xml:space="preserve" '
          f'style="paint-order:stroke;stroke:#ffffff;stroke-width:4px;stroke-linejoin:round">{esc(txt)}</text>')

def sequence(s, top, title, lanes, msgs, lane_w, x0):
    s.text(x0, top, title, size=17, weight='bold', fill='#222')
    hy = top + 16
    xs = {}
    for i, (key, label, col) in enumerate(lanes):
        cx = x0 + lane_w / 2 + i * lane_w
        xs[key] = cx
        f, st, t = C[col]
        s.raw(f'<rect x="{cx - lane_w/2 + 6}" y="{hy}" width="{lane_w - 12}" height="46" rx="8" fill="{f}" stroke="{st}" stroke-width="2"/>')
        lines = label.split('\n')
        for j, ln in enumerate(lines):
            s.text(cx, hy + 20 + j * 16, ln, size=12.5, weight='bold' if j == 0 else 'normal', fill=t, anchor='middle')
    y = hy + 70
    def st(m):
        base = m[4] if len(m) > 4 else 46
        if m[0] == m[1]:
            n = 1 + (len(m[3].split('\n')) if m[3] else 0)
            base = max(base, 26 + 15 * (n - 1) + 18)
        return base
    end = y + sum(st(m) for m in msgs) + 10
    for key, _, _ in lanes:
        s.line(xs[key], hy + 46, xs[key], end, colour='#bbb', width=1.5, dash=True)
    n = 1
    for m in msgs:
        a, b, label, note = m[:4]
        step = m[4] if len(m) > 4 else 46
        if a == b:   # self action: box
            x = xs[a]
            texts = [label] + (note.split('\n') if note else [])
            bw = max(len(t) for t in texts) * 7.1 + 46
            bh = 26 + 15 * (len(texts) - 1)
            step = max(step, bh + 18)
            s.raw(f'<rect x="{x - lane_w/2 + 14}" y="{y - 14}" width="{bw}" height="{bh}" rx="6" fill="#fff" stroke="#888" stroke-width="1.2"/>')
            s.raw(f'<circle cx="{x - lane_w/2 + 26}" cy="{y}" r="10" fill="#333"/>')
            s.text(x - lane_w/2 + 26, y + 4, str(n), size=11, weight='bold', fill='#fff', anchor='middle')
            s.text(x - lane_w/2 + 42, y + 4, label, size=12, weight='bold')
            if note:
                for k, ln in enumerate(note.split('\n')):
                    s.text(x - lane_w/2 + 42, y + 21 + k * 15, ln, size=11.5, mono=True, fill='#444')
        else:
            x1, x2 = xs[a], xs[b]
            s.arrow(x1, y + 6, x2 + (-4 if x2 > x1 else 4), y + 6, colour='#333')
            left = min(x1, x2)
            s.raw(f'<circle cx="{left + 16}" cy="{y - 8}" r="10" fill="#333"/>')
            s.text(left + 16, y - 4, str(n), size=11, weight='bold', fill='#fff', anchor='middle')
            halo(s, left + 32, y - 4, label, 12, 'bold', '#333', False)
            if note:
                for k, ln in enumerate(note.split('\n')):
                    halo(s, left + 32, y + 22 + k * 15, ln, 11.5, 'normal', '#7a4d00', True)
        y += step
        n += 1
    return end

W2 = 1500
s = Svg(W2, 1790, 'Identify and heartbeat LEDs: how they work, step by step')
s.text(W2/2, 34, 'Identify and heartbeat LEDs: how they work, step by step', size=23, weight='bold', fill='#222', anchor='middle')
s.text(W2/2, 58, 'Arrows are messages (HTTPS, D-Bus, or system calls); white boxes are work done inside one program. Numbers give the order.',
       size=13.5, fill='#555', anchor='middle')
legend(s, 74, [('teal', 'outside the board'), ('blue', 'standard OpenBMC / Linux'), ('green', 'added by us'),
               ('purple', 'Linux kernel'), ('grey', 'hardware')])
lanes_a = [('pc', 'Browser\n(web UI)', 'teal'), ('web', 'bmcweb\nRedfish server', 'blue'), ('gm', 'phosphor-ledmanager\nLED.GroupManager', 'blue'),
           ('map', 'Object mapper\nObjectMapper', 'blue'), ('si', 'LED stand-in\nLED.GpioStandIn', 'green'), ('k', 'Kernel\ngpiolib, gpio-omap', 'purple'),
           ('led', 'USR3 LED\nGPIO1_24', 'grey')]
LW = 208
msgs_a = [
    ('pc', 'web', 'HTTPS PATCH /redfish/v1/Systems/system', '{"LocationIndicatorActive": true}', 52),
    ('web', 'gm', 'D-Bus Properties.Set', 'groups/enclosure_identify_blink\n.Led.Group  Asserted = true', 60),
    ('gm', 'gm', 'look up the group in the config', 'member beaglebone_usr3_green:\nBlink, DutyOn 50, Period 1000\n(Priority Blink: nothing outranks it)', 72),
    ('gm', 'map', 'D-Bus GetObject', '…/led/physical/beaglebone_usr3_green\n[xyz.openbmc_project.Led.Physical]', 60),
    ('map', 'gm', 'reply: owner', '"xyz.openbmc_project.LED.GpioStandIn"', 50),
    ('gm', 'si', 'D-Bus Properties.Set  ×3', 'DutyOn = 50 (y)   Period = 1000 (q)\nState = "…Physical.Action.Blink" (s)', 60),
    ('si', 'si', 'start blinking USR3', 'on time = 1000 × 50 % = 500 ms\noff time = 500 ms, then repeat', 62),
    ('si', 'k', 'ioctl SET_VALUES on the held line', 'bit for line 24 = 1 … (500 ms) … = 0 …', 52),
    ('k', 'led', 'DATAOUT bit 24 = 1 / 0', 'USR3 blinks once a second', 52),
    ('gm', 'web', 'Set returns OK', '', 40),
    ('web', 'pc', 'HTTP success (2xx)', 'web UI switch shows ON', 52),
    ('pc', 'pc', 'switch OFF: same steps with false', '→ State = "…Action.Off" → line 0', 50),
]
end_a = sequence(s, 116, 'A.  Identify ON from the web UI (or any Redfish client)', lanes_a, msgs_a, LW, 20)

lanes_b = [('sd', 'systemd\n(PID 1)', 'blue'), ('map', 'Object mapper\nObjectMapper', 'blue'), ('si', 'LED stand-in\nLED.GpioStandIn', 'green'),
           ('gm', 'phosphor-ledmanager\nLED.GroupManager', 'blue'), ('bb', 'obmc-led-group-start\n@bmc_booted (busctl)', 'blue'),
           ('k', 'Kernel\ngpiolib, gpio-omap', 'purple'), ('led', 'USR0 LED\nGPIO1_21', 'grey')]
msgs_b = [
    ('sd', 'map', 'start ObjectMapper.service', '(after dbus-broker)', 46),
    ('sd', 'si', 'start bbb-led-standin.service', '/usr/local/bin/bbb-led-standin', 46),
    ('si', 'k', 'request 4 lines as outputs, value 0', '"[usr0 led]" … "[usr3 led]": all LEDs off', 50),
    ('si', 'si', 'publish 4 objects, THEN claim bus name', '…/led/physical/beaglebone_*_green\nxyz.openbmc_project.LED.GpioStandIn', 62),
    ('map', 'map', 'new name seen → introspect it', 'records the 4 LED objects + owner', 50),
    ('sd', 'sd', 'ExecStartPost: mapper wait …usr3', 'returns once the mapper knows it\n→ unit counts as "started"', 58),
    ('sd', 'gm', 'start LED.GroupManager.service', '', 40),
    ('gm', 'gm', 'read /etc/phosphor-led-manager/', 'led-group-config.json → publish\n3 groups, all Asserted = false', 58),
    ('sd', 'bb', 'multi-user.target reached → run it', '', 40),
    ('bb', 'gm', 'D-Bus Properties.Set', 'groups/bmc_booted  Asserted = true', 50),
    ('gm', 'map', 'GetObject …/beaglebone_heartbeat_green', '→ "xyz.openbmc_project.LED.GpioStandIn"', 50),
    ('gm', 'si', 'Set DutyOn 10, Period 1000, State Blink', '', 40),
    ('si', 'k', 'line 21: 1 for 100 ms, 0 for 900 ms, …', '', 40),
    ('k', 'led', 'DATAOUT bit 21', 'USR0: short flash every second', 52),
]
sequence(s, end_a + 46, 'B.  At every boot: "BMC booted" flash on USR0', lanes_b, msgs_b, LW, 20)
s.save(f'{OUT}/leds-sequences.svg')
