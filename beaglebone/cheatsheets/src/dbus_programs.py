"""Generate 'What D-Bus physically is' and 'What each OpenBMC program does'.
Usage: python3 dbus_programs.py <dir with lib.py> <out dir>"""
import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C
OUT = sys.argv[2]

def legend(s, y, items):
    lx = 20
    for col, lab in items:
        f, st, t = C[col]
        s.raw(f'<rect x="{lx}" y="{y}" width="22" height="16" rx="3" fill="{f}" stroke="{st}" stroke-width="2"/>')
        s.text(lx + 30, y + 13, lab, size=13)
        lx += 30 + len(lab) * 6.9 + 24

# =====================================================================
# Sheet 1: what D-Bus physically is
# =====================================================================
W, H = 1600, 1380
s = Svg(W, H, 'What D-Bus physically is')
s.text(W/2, 34, 'What D-Bus physically is (and is not)', size=24, weight='bold', fill='#222', anchor='middle')
s.text(W/2, 58, 'D-Bus is NOT a file of messages and NOT a database. It is one running program (dbus-broker) that ROUTES messages between other running programs.',
       size=14, fill='#555', anchor='middle')
legend(s, 74, [('blue', 'a running program (its own memory)'), ('yellow', 'dbus-broker (the router)'), ('orange', 'in RAM: lost at reboot'),
               ('green', 'on the eMMC: survives reboot'), ('grey', 'notes')])

# --- the picture: programs as separate memory boxes
s.text(20, 122, '1. THE PICTURE: separate programs, each with its own memory, connected to one router through a socket', size=14, weight='bold', fill='#333')
progs = [
    (40, 'bmcweb', 'PID 512 (example)', ['its memory: HTTP sessions,', 'Redfish routes …', '', 'owns NO objects; it only', 'ASKS other programs'], ':1.42', '(no well-known name)'),
    (440, 'phosphor-host-state-manager', 'PID 301 (example)', ['its memory holds its OBJECTS:', '/xyz/openbmc_project/state/host0', '  CurrentHostState = "…Off"', '  RequestedHostTransition = …', '  (+ methods, signals)'], ':1.17', 'xyz.openbmc_project.State.Host0'),
    (840, 'phosphor-ledmanager', 'PID 288 (example)', ['its memory holds its OBJECTS:', '/xyz/…/led/groups/bmc_booted', '  Asserted = true', '/xyz/…/led/groups/enclosure_identify…', '  Asserted = false'], ':1.9', 'xyz.openbmc_project.LED.GroupManager'),
    (1240, 'phosphor-objmgr (mapper)', 'PID 140 (example)', ['its memory: the directory', '"which name owns which', ' object path + interface"', '(built by asking everyone)', ''], ':1.3', 'xyz.openbmc_project.ObjectMapper'),
]
for x, name, pid, mem, uniq, wk in progs:
    s.box(x, 136, 340, 160, 'blue', name, [pid] + mem, line_size=12, line_gap=17)
    s.line(x + 170, 296, x + 170, 400, colour='#d48a00', width=3)
    s.raw(f'<rect x="{x+10}" y="336" width="320" height="40" rx="6" fill="#fff" stroke="#d48a00" stroke-width="1.5"/>')
    s.text(x + 170, 352, f'connection {uniq}', size=12, weight='bold', mono=True, anchor='middle')
    s.text(x + 170, 368, wk, size=10.5, mono=True, anchor='middle', fill='#555')

f, st, t = C['yellow']
s.raw(f'<rect x="40" y="400" width="1540" height="166" rx="12" fill="{f}" stroke="{st}" stroke-width="2.5"/>')
s.text(60, 424, 'dbus-broker  (one program, started by systemd as dbus.service / dbus-broker)', size=15, weight='bold', fill=t)
s.text(60, 446, 'Holds ONLY routing information, in its memory:', size=13)
tables = [('connections', [':1.3, :1.9, :1.17, :1.42 …', 'one per connected program']),
          ('name table', ['xyz.openbmc_project.State.Host0 → :1.17', 'xyz.openbmc_project.LED.GroupManager → :1.9']),
          ('subscriptions ("match rules")', ['who wants which signals, e.g.', 'mapper: every NameOwnerChanged']),
          ('security policy', ['who may own / call what, loaded from', '/usr/share/dbus-1/system.d/*.conf'])]
x = 60
for title, ls in tables:
    s.raw(f'<rect x="{x}" y="458" width="365" height="94" rx="8" fill="#ffffff" stroke="{st}" stroke-width="1.2"/>')
    s.text(x + 10, 478, title, size=13, weight='bold', fill=t)
    s.text(x + 10, 500, ls[0], size=11.5, mono=True)
    s.text(x + 10, 518, ls[1], size=11.5, mono=True)
    x += 378
s.text(60, 562 - 4, '', size=1)

# socket file
s.box(40, 584, 760, 104, 'orange', 'The only "file": /run/dbus/system_bus_socket', [
    'A Unix SOCKET: a file-shaped address. Programs "connect" to it like dialling a number.',
    'Nothing is stored in it; you can\'t cat it. ls -l shows type "s":  srw-rw-rw- … system_bus_socket',
    'It lives in /run (RAM). Recreated at every boot.'], line_size=12.5)
s.box(820, 584, 760, 104, 'green', 'Where data is SAVED: each program\'s own files, not D-Bus', [
    'host state manager → /var/lib/phosphor-state-manager/…   log manager → /var/lib/phosphor-logging/',
    'settings manager → /var/lib/phosphor-settings-manager/settings   network → /etc/systemd/network/',
    'At start-up each program reads its files and re-publishes its objects on D-Bus.'], line_size=12.2)

# --- part 2: one Get, step by step
y0 = 716
s.text(20, y0, '2. ONE QUESTION, STEP BY STEP: bmcweb wants CurrentHostState (for "PowerState" in Redfish)', size=14, weight='bold', fill='#333')
steps = [
    ('bmcweb', 'writes a message into its socket connection:', 'to xyz.openbmc_project.State.Host0, /xyz/…/state/host0,', 'Properties.Get("xyz.openbmc_project.State.Host", "CurrentHostState")'),
    ('dbus-broker', 'reads it, checks the security policy, looks up the name table:', 'xyz.openbmc_project.State.Host0 → :1.17', 'and copies the message to connection :1.17'),
    ('host state manager', 'its event loop wakes up, finds the property in ITS OWN memory,', 'writes a reply: (s) "xyz.openbmc_project.State.Host.HostState.Off"', ''),
    ('dbus-broker', 'routes the reply back to :1.42 (bmcweb)', '', ''),
    ('bmcweb', 'reads "…HostState.Off" and puts "PowerState": "Off"', 'into the Redfish JSON it sends to your browser', ''),
]
y = y0 + 16
for i, (who, a, b, c) in enumerate(steps):
    col = 'yellow' if who == 'dbus-broker' else 'blue'
    f, st, t = C[col]
    s.raw(f'<rect x="20" y="{y}" width="1560" height="44" rx="8" fill="{f}" stroke="{st}" stroke-width="1.5"/>')
    s.raw(f'<circle cx="44" cy="{y+22}" r="13" fill="#333"/>')
    s.text(44, y + 27, str(i + 1), size=13, weight='bold', fill='#fff', anchor='middle')
    s.text(70, y + 27, who, size=13.5, weight='bold', fill=t)
    s.text(240, y + 18, a, size=12.5)
    if b or c:
        s.text(240, y + 36, (b + '   ' + c).strip(), size=11.8, mono=True, fill='#7a4d00')
    y += 52
s.text(20, y + 10, 'Takes well under a millisecond. Nothing is written anywhere: the value came from the host state manager\'s memory. If that program isn\'t running, step 2 fails with "name has no owner".',
       size=12.5, italic=True, fill='#555')

# --- part 3: signals + kinds of message
y0 = y + 40
s.text(20, y0, '3. THE FOUR KINDS OF MESSAGE', size=14, weight='bold', fill='#333')
kinds = [('method_call', 'a request to ONE program: "Get this", "Set that", "GetObject(…)", "CreateUser(…)"'),
         ('method_return', 'the answer to one call (the value, or just "done")'),
         ('error', 'the call failed: e.g. org.freedesktop.DBus.Error.ServiceUnknown, InvalidArgs, AccessDenied'),
         ('signal', 'an announcement to EVERYONE subscribed: "PropertiesChanged", "InterfacesAdded", "NameOwnerChanged".  '
                    'The broker copies it to each subscriber; nobody replies.')]
y = y0 + 14
for k, d in kinds:
    s.text(36, y + 14, k, size=13, weight='bold', mono=True, fill='#7a4d00')
    s.text(190, y + 14, d, size=12.5)
    y += 24

# --- part 4: misconceptions
y0 = y + 22
s.box(20, y0, 1560, 196, 'grey', 'Is D-Bus…', [], title_size=15)
mis = [('a file you read/write like a message board?', 'No. Messages pass through the broker and are gone. The socket file is only the address to connect to.'),
       ('a database or registry of values?', 'No. Values live inside each program. Ask the program (through the broker) to get them.'),
       ('shared memory?', 'No. Message bytes are copied: sender → broker → receiver, through sockets.'),
       ('permanent?', 'No. When a program exits, its name and objects disappear from the bus at once.'),
       ('the same as the network?', 'No. The system bus is local to the BMC. bmcweb is the bridge between the network (HTTPS) and D-Bus.'),
       ('so what IS it?', 'A message ROUTER + a NAME registry + a SECURITY policy, run by dbus-broker, plus an agreed message format.')]
y = y0 + 46
for q, a in mis:
    s.text(36, y, q, size=12.8, weight='bold')
    s.text(420, y, a, size=12.8)
    y += 21
s.rich(36, y0 + 184, [('On the board: ', False, True), ('ls -l /run/dbus/system_bus_socket', True, False), ('   ', False, False), ('busctl list', True, False),
                      (' (names, owners, PIDs)   ', False, False), ('busctl monitor', True, False), (' (watch messages live)   ', False, False),
                      ('busctl status xyz.openbmc_project.State.Host0', True, False)], size=12.5)
s.save(f'{OUT}/dbus-explained.svg')

# =====================================================================
# Sheet 2: what each program does
# =====================================================================
cards = [
    ('blue', 'bmcweb', 'web server: the Redfish API + the web UI files', '(no well-known name: a client only)',
     ['HTTPS on port 443; your login', 'certs /etc/ssl/certs/https/server.pem', 'web UI files /usr/share/www/'],
     ['nothing of its own: it ASKS the others', '(see "D-Bus calls it makes")'],
     ['Get/Set properties + call methods on', 'every other program, then answers', 'with Redfish JSON']),
    ('blue', 'ipmid + netipmid', 'the older IPMI protocol (ipmitool)', 'xyz.openbmc_project.Control.Host',
     ['netipmid: UDP port 623 from the network', 'ipmid: host\'s KCS/BT interface (none here)'],
     ['/xyz/openbmc_project/Ipmi …'],
     ['turns IPMI commands into the same', 'D-Bus calls (power, sensors, users)']),
    ('blue', 'object mapper (mapperx)', 'the directory of everything on D-Bus', 'xyz.openbmc_project.ObjectMapper',
     ['every program appearing/leaving the bus', '(NameOwnerChanged, InterfacesAdded),', 'then asks each one to describe itself'],
     ['/xyz/openbmc_project/object_mapper', 'GetObject, GetSubTree, GetAncestors'],
     ['nothing on disk (memory only)', 'answers "who owns path X?"']),
    ('blue', 'host state manager', 'is the server\'s OS off / running / quiesced?', 'xyz.openbmc_project.State.Host0',
     ['systemd: which obmc-host-*@0 targets', 'finished (startmin → Running, stop → Off)'],
     ['/xyz/openbmc_project/state/host0', 'CurrentHostState, RequestedHostTransition'],
     ['starts obmc-host-start/-shutdown/-reboot', '/var/lib/phosphor-state-manager/', '  (last requested transition)']),
    ('blue', 'chassis state manager', 'is the chassis (power supply) on or off?', 'xyz.openbmc_project.State.Chassis0',
     ['systemd: obmc-chassis-poweron/-poweroff', 'targets finishing'],
     ['/xyz/openbmc_project/state/chassis0', 'CurrentPowerState, RequestedPowerTransition', 'LastStateChangeTime, POH counter'],
     ['starts obmc-chassis-* targets', '/var/lib/phosphor-state-manager/', '  chassis0-POHCounter, -StateChangeTime']),
    ('blue', 'BMC state manager', 'is the BMC itself ready? why did it last reboot?', 'xyz.openbmc_project.State.BMC',
     ['multi-user.target reached → Ready', '/sys/class/watchdog/watchdog0/bootstatus', '/run/boot-device'],
     ['/xyz/openbmc_project/state/bmc0', 'CurrentBMCState, RequestedBMCTransition', 'LastRebootCause'],
     ['Reboot request → starts reboot.target']),
    ('blue', 'LED group manager', 'LED GROUPS: identify, booted, fault …', 'xyz.openbmc_project.LED.GroupManager',
     ['/etc/phosphor-led-manager/', '  led-group-config.json (at start)', 'Set Asserted from bmcweb, units, you'],
     ['/xyz/openbmc_project/led/groups/<name>', 'Asserted (b)'],
     ['Set State/DutyOn/Period on each member', 'LED\'s owner (found via the mapper)']),
    ('blue', 'LED controller (phosphor-led-sysfs)', 'PHYSICAL LEDs from the kernel', 'xyz.openbmc_project.LED.Controller',
     ['/sys/class/leds/<name> (udev tells it', 'when the kernel creates an LED)'],
     ['/xyz/openbmc_project/led/physical/<name>', 'State, DutyOn, Period, Color'],
     ['brightness / trigger files in', '/sys/class/leds/<name>/', '(idle on our kernel; our stand-in instead)']),
    ('blue', 'log manager (phosphor-logging)', 'the event log', 'xyz.openbmc_project.Logging',
     ['programs asking to log an event', '(Create method, or their log calls)'],
     ['/xyz/openbmc_project/logging/entry/<N>', 'Message, Severity, Timestamp, Resolved', 'DeleteAll'],
     ['each entry saved in', '/var/lib/phosphor-logging/']),
    ('blue', 'network manager (phosphor-networkd)', 'network settings for the web UI / Redfish', 'xyz.openbmc_project.Network',
     ['the kernel\'s interfaces + addresses', 'systemd-networkd\'s state'],
     ['/xyz/openbmc_project/network/eth0 …', 'IP addresses, DHCP, MAC, DNS, hostname'],
     ['.network files in /etc/systemd/network/', 'then tells systemd-networkd to reload']),
    ('blue', 'user manager', 'BMC user accounts, roles, password rules', 'xyz.openbmc_project.User.Manager',
     ['/etc/passwd, /etc/login.defs', '/etc/security/*.conf (lockout, quality)'],
     ['/xyz/openbmc_project/user/<name>', 'UserPrivilege, UserGroups, UserEnabled', 'CreateUser method'],
     ['user accounts (/etc/passwd, group, shadow)', 'PAM rule files; /var/lib/usr_mgr.conf']),
    ('blue', 'settings manager', 'stores settings other programs read', 'xyz.openbmc_project.Settings',
     ['its saved file at start-up'],
     ['/xyz/openbmc_project/control/host0/…', '  power_restore_policy, boot, auto_reboot', '/xyz/openbmc_project/time/sync_method'],
     ['/var/lib/phosphor-settings-manager/', '  settings (every change)']),
    ('blue', 'inventory manager', 'the parts list (FRUs): model, serial …', 'xyz.openbmc_project.Inventory.Manager',
     ['other programs (FRU readers) calling', 'its Notify method to add/update items'],
     ['/xyz/openbmc_project/inventory/…', 'Model, SerialNumber, Present …'],
     ['/var/lib/phosphor-inventory-manager/', '(nearly empty on our board)']),
    ('blue', 'time manager', 'BMC clock: NTP or manual', 'xyz.openbmc_project.Time.Manager',
     ['setting /xyz/…/time/sync_method', '(NTP or Manual)'],
     ['/xyz/openbmc_project/time/bmc', 'Elapsed (the current time)'],
     ['asks systemd-timedated (D-Bus):', 'SetNTP / SetTime']),
    ('blue', 'software manager', 'firmware versions + updates', 'xyz.openbmc_project.Software.Manager',
     ['/etc/os-release (running version)', 'uploaded images in /tmp/images'],
     ['/xyz/openbmc_project/software/<id>', 'Version, Purpose, Activation'],
     ['/var/lib/phosphor-bmc-code-mgmt/', 'writes flash on flash-chip boards', '(not our SD/eMMC layout)']),
    ('blue', 'dump manager', 'debug "black box" snapshots', 'xyz.openbmc_project.Dump.Manager',
     ['CreateDump requests (web UI, Redfish)'],
     ['/xyz/openbmc_project/dump/bmc/entry/<N>'],
     ['/var/lib/phosphor-debug-collector/dumps', '(archives of logs + state)']),
    ('blue', 'health monitor', 'the BMC\'s own CPU / memory / storage use', 'xyz.openbmc_project.HealthMon',
     ['/proc/stat, /proc/meminfo, disk usage', '/etc/healthMon/bmc_health_config.json'],
     ['/xyz/openbmc_project/metric/bmc/…', 'CPU_User, Memory_Free, Storage_RW …'],
     ['nothing on disk; values + thresholds', 'on D-Bus']),
    ('blue', 'telemetry', 'Redfish metric reports + triggers', 'xyz.openbmc_project.Telemetry',
     ['sensor values from D-Bus', '(…/sensors/…), on a schedule'],
     ['/xyz/openbmc_project/Telemetry/Reports/…', '/xyz/openbmc_project/Telemetry/Triggers/…'],
     ['/var/lib/telemetry/Reports, Triggers']),
    ('blue', 'phosphor-hwmon (sensors)', 'sensors from kernel hwmon drivers', 'xyz.openbmc_project.Hwmon-<id>…',
     ['/sys/class/hwmon/hwmonN/*_input', 'per-device config in /etc/default/obmc/hwmon/'],
     ['/xyz/openbmc_project/sensors/<type>/<name>', 'Value, thresholds'],
     ['nothing on disk', '(IDLE here: no sensors configured)']),
    ('green', 'bbb-led-standin (ours)', 'stand-in for the LED controller', 'xyz.openbmc_project.LED.GpioStandIn',
     ['Set calls from the LED group manager'],
     ['/xyz/openbmc_project/led/physical/beaglebone_*', 'State, DutyOn, Period, Color'],
     ['GPIO lines "[usr0 led]" … "[usr3 led]"', 'through /dev/gpiochip0']),
]
COLS, CW, CH, GX, GY = 4, 384, 222, 20, 128
rows = (len(cards) + COLS - 1) // COLS
W2, H2 = 1600, GY + rows * (CH + 12) + 150
s = Svg(W2, H2, 'What each OpenBMC program does')
s.text(W2/2, 34, 'What each OpenBMC program does: what it watches, what it publishes, what it changes', size=23, weight='bold', fill='#222', anchor='middle')
s.text(W2/2, 58, 'One card per program running on our BeagleBone. File paths and object paths come from the programs themselves (strings in our image\'s binaries) and their unit files.',
       size=13.5, fill='#555', anchor='middle')
lx = 20
for lab, col in [('WATCHES / READS: its inputs', '#2a6f9e'), ('PUBLISHES on D-Bus: objects others can read/set', '#7a4d00'), ('CHANGES / WRITES: its effects', '#2e7d32')]:
    s.raw(f'<rect x="{lx}" y="78" width="14" height="14" rx="3" fill="{col}"/>')
    s.text(lx + 22, 90, lab, size=13)
    lx += 24 + len(lab) * 6.9 + 30
s.text(W2 - 20, 90, 'the second line of each card = the D-Bus name it claims', size=12.5, fill='#555', anchor='end', italic=True)

for i, (col, name, job, bus, reads, pubs, writes) in enumerate(cards):
    x = GX + (i % COLS) * (CW + 8)
    y = GY + (i // COLS) * (CH + 12)
    f, st, t = C[col]
    s.raw(f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" rx="10" fill="{f}" stroke="{st}" stroke-width="2"/>')
    s.text(x + 12, y + 20, name, size=14, weight='bold', fill=t)
    s.text(x + 12, y + 37, bus, size=10.8, mono=True, fill='#555')
    s.text(x + 12, y + 55, job, size=12.2, italic=True, fill='#222')
    yy = y + 74
    for label, items, lc in [('WATCHES', reads, '#2a6f9e'), ('PUBLISHES', pubs, '#7a4d00'), ('CHANGES', writes, '#2e7d32')]:
        s.raw(f'<rect x="{x+10}" y="{yy-11}" width="6" height="{len(items)*14+2}" rx="2" fill="{lc}"/>')
        for k, it in enumerate(items):
            s.text(x + 22, yy + k * 14, it, size=10.9, mono=True, fill='#222')
        yy += len(items) * 14 + 8

by = GY + rows * (CH + 12) + 6
s.box(20, by, 1560, 126, 'grey', 'How they fit together (read a card, then follow the arrows in your head)', [
    (('From outside, requests arrive through bmcweb (web/Redfish), IPMI, or you over SSH (busctl, obmcutil). They become D-Bus calls to the program that owns that job.', False, False)),
    (('Programs find each other through the ', False, False), ('object mapper', False, True), (', then talk directly (via dbus-broker). None of them stores anything in D-Bus itself.', False, False)),
    (('Power on/off is done by ', False, False), ('systemd targets', False, True), (' that the state managers start (see the targets cheat sheet); the state managers then report the result.', False, False)),
    (('Anything that must survive a reboot is in that program\'s own file (', False, False), ('/var/lib/…', True, False), (' or ', False, False), ('/etc/…', True, False), (').  Try: ', False, False),
     ('busctl tree <name>', True, False), (' and ', False, False), ('busctl introspect <name> <path>', True, False), (' for any card.', False, False)),
], line_gap=21, line_size=12.8)
s.save(f'{OUT}/openbmc-programs.svg')
