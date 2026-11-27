"""Generate the OpenBMC targets cheat sheet.
Usage: python3 targets.py <dir with lib.py> <out dir>"""
import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C, esc, MONO
OUT = sys.argv[2]

W, H = 1600, 1440
s = Svg(W, H, 'OpenBMC systemd targets cheat sheet')
s.text(W/2, 34, 'OpenBMC targets: how host and chassis power are driven', size=24, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'A request becomes a state-manager transition, the state manager starts a systemd TARGET, and every service hooked into that target runs. '
       'All names from our image.', size=13.5, fill='#555', anchor='middle')

def legend(y):
    lx = 20
    for col, lab in [('teal', 'outside the board / users'), ('blue', 'standard OpenBMC (in the image)'), ('grey', 'notes and reference')]:
        f, st, t = C[col]
        s.raw(f'<rect x="{lx}" y="{y}" width="22" height="16" rx="3" fill="{f}" stroke="{st}" stroke-width="2"/>')
        s.text(lx + 30, y + 13, lab, size=13)
        lx += 30 + len(lab) * 6.9 + 26
    s.rich(lx, y + 13, [('T ', True, True), ('= target (a milestone)     ', False, False), ('S ', True, True), ('= service (does work)     ', False, False),
                        ('@0', True, True), (' = instance 0: the first chassis / host', False, False)], size=13)
legend(74)

# ------------------------------------------------------------------ row 1: who asks
y = 104
s.text(20, y + 6, '1. WHO ASKS', size=13, weight='bold', fill='#2a9d9d')
reqs = [('Web UI', ['Operations → Server power', 'operations (buttons)']),
        ('Redfish', ['POST …/Systems/system/Actions/', 'ComputerSystem.Reset {ResetType}']),
        ('obmcutil (on the BMC)', ['poweron  poweroff', 'chassison  chassisoff  state']),
        ('Other', ['IPMI "chassis power …";', 'power-restore policy at BMC boot'])]
x = 20
for t, ls in reqs:
    s.box(x, y + 14, 238, 76, 'teal', t, ls, center=True, line_size=12)
    x += 248
# Redfish ResetType table
tx, ty = 1020, y + 14
s.raw(f'<rect x="{tx}" y="{ty}" width="560" height="196" rx="10" fill="#f6f6f6" stroke="#888" stroke-width="2"/>')
s.text(tx + 12, ty + 20, 'Redfish ResetType → D-Bus transition (bmcweb systems.hpp)', size=13, weight='bold', fill='#333')
rows = [('On / ForceOn', 'Host.Transition.On'), ('GracefulShutdown', 'Host.Transition.Off'),
        ('ForceOff', 'Chassis.Transition.Off'), ('GracefulRestart', 'Host.Transition.GracefulWarmReboot'),
        ('ForceRestart', 'Host.Transition.ForceWarmReboot'), ('PowerCycle', 'Host.Transition.Reboot'),
        ('(obmcutil chassison/off)', 'Chassis.Transition.On / Off'), ('(obmcutil poweron/off)', 'Host.Transition.On / Off')]
ry = ty + 42
for a, b in rows:
    s.text(tx + 14, ry, a, size=12, mono=True, weight='bold')
    s.text(tx + 236, ry, '→ ' + b, size=12, mono=True)
    ry += 19
s.arrow(510, y + 92, 510, y + 222)
s.text(520, y + 160, 'set property  Requested…Transition', size=11.5, fill='#7a4d00', mono=True)
s.text(520, y + 176, 'on the state manager (over D-Bus)', size=11.5, fill='#7a4d00', mono=True)

# ------------------------------------------------------------------ row 2: state managers
y = 330
s.text(20, y + 6, '2. STATE MANAGERS (phosphor-state-manager) — turn a requested transition into a target, and a reached target into a state', size=13, weight='bold', fill='#4a6fd1')
sm = [
    ('Host  /xyz/openbmc_project/state/host0', 'xyz.openbmc_project.State.Host', [
        ('RequestedHostTransition', ''),
        ('  On', 'obmc-host-start@0'), ('  Off', 'obmc-host-shutdown@0'), ('  Reboot', 'obmc-host-reboot@0'),
        ('  GracefulWarmReboot', 'obmc-host-warm-reboot@0'), ('  ForceWarmReboot', 'obmc-host-force-warm-reboot@0'),
        ('CurrentHostState ← reached:', ''),
        ('  Running', 'obmc-host-startmin@0'), ('  Off', 'obmc-host-stop@0'), ('  Quiesced', 'obmc-host-quiesce@0'),
        ('  DiagnosticMode', 'obmc-host-diagnostic-mode@0')]),
    ('Chassis  …/state/chassis0', 'xyz.openbmc_project.State.Chassis', [
        ('RequestedPowerTransition', ''),
        ('  On', 'obmc-chassis-poweron@0'), ('  Off', 'obmc-chassis-hard-poweroff@0'), ('  PowerCycle', 'obmc-chassis-powercycle@0'),
        ('CurrentPowerState ← reached:', ''),
        ('  On', 'obmc-chassis-poweron@0'), ('  Off', 'obmc-chassis-poweroff@0'),
        ('Power lost while on:', ''), ('', 'obmc-chassis-blackout@0')]),
    ('BMC  …/state/bmc0', 'xyz.openbmc_project.State.BMC', [
        ('RequestedBMCTransition', ''), ('  Reboot', 'reboot.target  (systemd)'),
        ('CurrentBMCState Ready ← reached:', ''), ('', 'multi-user.target'),
        ('Quiesced (a critical service failed):', ''), ('', 'obmc-bmc-service-quiesce@0')]),
]
x = 20
widths = [560, 530, 450]
for (title, iface, items), w in zip(sm, widths):
    hh = 44 + len(items) * 18 + 12
    s.box(x, y + 16, w, 252, 'blue', title, [], title_size=13.5, title_mono=True)
    s.text(x + 12, y + 56, iface, size=12, mono=True, fill='#555')
    iy = y + 78
    for a, b in items:
        if b == '':
            s.text(x + 12, iy, a, size=12, mono=True, weight='bold', fill='#1d3b8a')
        else:
            s.text(x + 12, iy, a, size=12, mono=True)
            s.text(x + (205 if w > 500 else 170), iy, '→ ' + b + ('' if b.endswith(')') or b.endswith('.target') else '.target'), size=12, mono=True, fill='#4b1d7a')
        iy += 17
    x += w + 10
s.text(20, y + 290, 'They start a target with systemd\'s StartUnit (over D-Bus), and watch systemd\'s "job done" signals to update Current…State.', size=12.5, fill='#555', italic=True)

# ------------------------------------------------------------------ row 3: trees
def tree(x, y, w, title, items, colour='blue'):
    f, st, t = C[colour]
    s.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{len(items)*19 + 48}" rx="10" fill="#fbfbfb" stroke="{st}" stroke-width="2"/>')
    s.text(x + 12, y + 22, title, size=14, weight='bold', fill=t)
    ty = y + 46
    for depth, rel, kind, name, note in items:
        xx = x + 14 + depth * 20
        if depth > 0:
            s.line(xx - 13, ty - 13, xx - 13, ty - 4, colour='#bbb', width=1.4)
            s.line(xx - 13, ty - 4, xx - 4, ty - 4, colour='#bbb', width=1.4)
        cx = xx
        if rel:
            s.text(cx, ty, rel, size=11, fill='#888', italic=True)
            cx += len(rel) * 5.6 + 6
        tag_col = '#4b1d7a' if kind == 'T' else '#1c5e2e' if kind == 'S' else '#888'
        if kind in ('T', 'S'):
            s.raw(f'<rect x="{cx}" y="{ty-11}" width="14" height="14" rx="3" fill="{tag_col}"/>')
            s.text(cx + 7, ty, kind, size=10, weight='bold', fill='#fff', anchor='middle')
            cx += 20
        s.text(cx, ty, name, size=11.8, mono=True, weight='bold' if kind == 'T' else 'normal',
               fill='#222' if kind in ('T', 'S') else '#666')
        if note:
            s.text(cx + len(name) * 7.05 + 10, ty, note, size=11.2, fill='#7a4d00', italic=True)
        ty += 19
    return y + len(items) * 19 + 48

y = 638
s.text(20, y, '3. WHAT EACH TARGET PULLS IN (our image\'s .requires/.wants folders, instance @0)', size=13, weight='bold', fill='#4a6fd1')
on = [
    (0, '', 'T', 'obmc-host-start@0.target', 'Host On'),
    (1, 'requires', 'T', 'obmc-host-startmin@0.target', '= host "Running" when reached'),
    (2, 'requires', 'T', 'obmc-chassis-poweron@0.target', 'chassis power on'),
    (3, 'requires', 'S', 'obmc-power-start@0.service', 'THE power switch: setPowerState 1'),
    (3, 'requires', 'S', 'phosphor-set-chassis-transition-to-on@0', ''),
    (3, 'requires', 'S', 'phosphor-wait-poweron-blocks.service', ''),
    (3, 'wants', 'T', 'obmc-power-start-pre@0 → -start@0 → -on@0', 'sync points'),
    (3, 'wants', 'S', 'obmc-led-group-start@power_on', 'power LED group'),
    (3, 'wants', 'S', 'phosphor-fan-control-init@0, fan-monitor-init', ''),
    (3, 'wants', 'S', 'phosphor-create-chassis-poweron-log@0 …', ''),
    (3, 'on failure', 'T', 'obmc-chassis-poweroff@0.target', ''),
    (2, 'wants', 'T', 'obmc-host-start-pre@0 → -starting@0 → -started@0', 'sync points'),
    (2, 'wants', 'S', 'phosphor-set-host-transition-to-running@0', ''),
    (2, 'wants', 'S', 'obmc-enable-host-watchdog@0, phosphor-watchdog@poweron', ''),
    (1, 'requires', 'S', 'phosphor-reset-host-reboot-attempts@0', ''),
    (1, 'on failure', 'T', 'obmc-host-quiesce@0.target', ''),
]
off = [
    (0, '', 'T', 'obmc-host-shutdown@0.target', 'Host Off (graceful)'),
    (1, 'requires', 'S', 'xyz.openbmc_project.Ipmi.Internal.SoftPowerOff', 'ask the OS to shut down'),
    (1, 'requires', 'T', 'obmc-host-stop@0.target', '= host "Off" when reached'),
    (2, 'wants', 'T', 'obmc-host-stop-pre@0 → -stopping@0 → -stopped@0', 'sync points'),
    (2, 'wants', 'S', 'phosphor-set-host-transition-to-off@0', ''),
    (1, 'requires', 'T', 'obmc-chassis-poweroff@0.target', '= chassis "Off"'),
    (2, 'requires', 'S', 'obmc-power-stop@0.service', 'THE power switch: setPowerState 0'),
    (2, 'requires', 'S', 'obmc-powered-off@0, phosphor-set-chassis-…-to-off@0', ''),
    (2, 'requires', 'T', 'obmc-host-stop@0.target', ''),
    (2, 'wants', 'T', 'obmc-power-stop-pre@0 → -stop@0 → -off@0', 'sync points'),
    (2, 'wants', 'S', 'obmc-led-group-stop@power_on, phosphor-clear-one-time@0', ''),
    (1, 'on failure', 'T', 'obmc-chassis-poweroff@0.target', ''),
    (0, '', '', '', ''),
    (0, '', 'T', 'obmc-chassis-hard-poweroff@0.target', 'Chassis Off (ForceOff)'),
    (1, 'requires', 'T', 'obmc-chassis-poweroff@0.target', 'no OS shutdown'),
    (0, '', 'T', 'obmc-host-reboot@0.target', 'Host Reboot / PowerCycle'),
    (1, 'requires', 'T', 'obmc-host-shutdown@0.target', ''),
    (1, 'requires', 'S', 'phosphor-reboot-host@0.service', 'waits 5 s, then starts host-startmin@0'),
]
e1 = tree(20, y + 12, 770, 'Power ON: Host.Transition.On  →  obmc-host-start@0.target', on)
e2 = tree(800, y + 12, 780, 'Power OFF / reboot', off)

# ------------------------------------------------------------------ row 4: notes
y = max(e1, e2) + 18
s.box(20, y, 520, 238, 'grey', 'How to read the target files', [
    (('Requires=', True, True), ('  must succeed (or this target fails)', False, False)),
    (('Wants=', True, True), ('     start it too, failure is OK', False, False)),
    (('After= / Before=', True, True), ('  order only, no "start"', False, False)),
    (('Conflicts=', True, True), ('  starting one stops the other:', False, False)),
    '     poweron ⟷ poweroff, host-startmin ⟷ host-stop',
    (('OnFailure=', True, True), ('  fallback if it fails (e.g. → poweroff)', False, False)),
    (('…-pre / -starting / -started', True, True), ('  empty "sync point"', False, False)),
    '   targets: hook a service in at the right moment with',
    (('   WantedBy=obmc-host-starting@0.target', True, False), (' + Before/After', False, False)),
    (('@%i', True, True), (' templates: one file serves chassis0, chassis1 …', False, False)),
], line_gap=20, line_size=12.5)
s.box(550, y, 520, 238, 'grey', 'Other OpenBMC targets in our image', [
    (('host-warm-reboot / -force-warm-reboot', True, False), (': reboot w/o power cycle', False, False)),
    (('host-quiesce / -graceful-quiesce', True, False), (': hold, collect info', False, False)),
    (('host-crash / host-timeout', True, False), (' (watchdog) → quiesce', False, False)),
    (('host-diagnostic-mode', True, False), (': diagnostic collection', False, False)),
    (('chassis-powercycle', True, False), ('   chassis-blackout', True, False), (': power lost', False, False)),
    (('chassis-powerreset / host-reset', True, False), (': BMC rebooted while the', False, False)),
    '    host was on: re-detect, don\'t power it off',
    (('chassis-powered-off', True, False), ('   bmc-service-quiesce', True, False)),
    (('fan-control-ready@0', True, False), (' (fan control + monitor)  ', False, False), ('fans-ready', True, False)),
    'All names start with obmc- and end with .target.',
], line_gap=20, line_size=12.5)
s.box(1080, y, 500, 238, 'grey', 'On our BeagleBone', [
    'No host, and nothing implements the power switch',
    (('(', False, False), ('org.openbmc.control.Power', True, False), (' on ', False, False), ('/org/openbmc/control/power0', True, False), (')', False, False)),
    (('→ ', False, False), ('obmc-power-start@0.service', True, False), (' should fail, so', False, False)),
    (('chassis-poweron fails → OnFailure → chassis-poweroff', True, False)),
    'and "Server power operations" ends up Off (not tested).',
    'A real board adds a power-control program (e.g.',
    'x86-power-control, phosphor-power-sequencer) or its',
    (('own services ', False, False), ('WantedBy=obmc-chassis-poweron@0.target', True, False)),
    'that drive the power-enable GPIOs.',
], line_gap=20, line_size=12.5)

y += 252
s.box(20, y, 1560, 108, 'grey', 'Commands (on the board)', [], title_size=14)
cmds = [('obmcutil state', 'BMC, chassis, host states'), ('obmcutil poweron | poweroff | chassisoff', 'request a transition'),
        ("systemctl list-units 'obmc-*'", 'targets/services now active'), ('systemctl list-dependencies obmc-host-start@0.target', 'the tree above, live'),
        ('systemctl cat obmc-chassis-poweron@0.target', 'one target file'), ('journalctl -b | grep -i target', 'when targets were reached')]
cx, cy = 34, y + 46
for i, (c, d) in enumerate(cmds):
    xx = cx + (i % 2) * 780
    yy = cy + (i // 2) * 22
    s.text(xx, yy, c, size=12, mono=True, weight='bold')
    s.text(xx + len(c) * 7.6 + 14, yy, d, size=11.5, italic=True, fill='#2e7d32')
s.save(f'{OUT}/openbmc-targets.svg')
