"""Generate the GPIO-toggle layer diagrams (C and C++).
Usage: python3 gpio_flow.py <dir with lib.py> <out dir>"""
import sys; sys.path.insert(0, sys.argv[1])
from lib import Svg, C
OUT = sys.argv[2]

PHASES = ['1. Find the line by name', '2. Reserve it as an output (start low)',
          '3. Toggle: set 1 / 0, sleep, repeat', '4. Release (end, or Ctrl-C)']

KERNEL_ROWS = [
    ('purple', 'Kernel: VFS +\nGPIO char device\n(gpiolib-cdev)', [
        ['gpio_chrdev_open()', 'gpio_ioctl() → by code:', ' chipinfo_get()', ' lineinfo_get()    (v2)', ' lineinfo_get_v1() (v1)'],
        ['gpio_ioctl() → by code:', ' linereq_create()    (v2)', ' linehandle_create() (v1)', 'both: gpiod_request_user()', 'return NEW fd = "line handle"'],
        ['ioctl on the line handle:', ' linereq_ioctl() →', '  linereq_set_values()  (v2)', ' linehandle_ioctl()     (v1)'],
        ['close(handle) →', ' linereq_release()    (v2)', ' linehandle_release() (v1)', ' → gpiod_free()'],
    ]),
    ('purple', 'Kernel:\ngpiolib core\n(generic)', [
        ['line names come from the', 'device tree (gpio-line-names);', 'owner shown if requested'],
        ['gpiod_request_commit():', ' mark REQUESTED (else EBUSY)', ' → gc->request()', 'gpiochip_direction_output()', ' → gc->direction_output()'],
        ['gpiod_set_array_value_complex()', '→ gpiochip_set_multiple()', '→ gc->set_multiple()'],
        ['clear REQUESTED', '→ gc->free()'],
    ]),
    ('purple', 'Kernel:\ngpio-omap driver\n(TI-specific)', [
        ['not involved', '(no register access)'],
        ['omap_gpio_request():', ' bank clock on (pm_runtime)', 'omap_gpio_output():', ' write start value, then', ' set direction = output'],
        ['omap_gpio_set_multiple():', ' read DATAOUT, change bit 24,', ' write it back (spinlock held)'],
        ['omap_gpio_free():', ' direction = INPUT', ' bank clock may turn off'],
    ]),
    ('grey', 'Hardware:\nGPIO1 registers\n@ 0x4804C000', [
        ['—'],
        ['CLEARDATAOUT 0x4804C190 ← 1<<24', '  (start value 0)', 'OE 0x4804C134: bit 24 → 0', '  (0 = output)'],
        ['DATAOUT 0x4804C13C', '  bit 24 = 1  or  0'],
        ['OE 0x4804C134: bit 24 → 1', '  (1 = input)'],
    ]),
    ('grey', 'Pin GPIO1_24\n→ USR3 LED', [
        ['—'],
        ['pin drives 0 V: LED off', '(pad mux 0x44E10860 = mode 7)'],
        ['3.3 V: LED on / 0 V: LED off', 'pin stays an OUTPUT the', 'whole time: no glitch'],
        ['pin not driven; pad pull-down', 'holds it at 0 V: LED off'],
    ]),
]

def draw(title, subtitle, user_rows, notes, fname):
    LW, CW, GAP = 190, 320, 8
    X0 = 20
    W = X0 + LW + 4 * (CW + GAP) + 12
    LH = 15.5
    def row_h(cells):
        return max(len(c) for c in cells) * LH + 18
    rows = user_rows + [None] + KERNEL_ROWS
    H = 170 + sum(row_h(r[2]) + GAP if r else 34 for r in rows) + 24 + len(notes) * 20 + 6
    s = Svg(W, int(H), title)
    s.text(W / 2, 34, title, size=24, weight='bold', fill='#222', anchor='middle')
    s.text(W / 2, 58, subtitle, size=14, fill='#555', anchor='middle')
    # legend
    lx = X0
    for col, lab in [('green', 'your code'), ('blue', 'libraries (not yours)'), ('purple', 'Linux kernel'), ('grey', 'hardware')]:
        f, st, t = C[col]
        s.raw(f'<rect x="{lx}" y="76" width="22" height="16" rx="3" fill="{f}" stroke="{st}" stroke-width="2"/>')
        s.text(lx + 30, 89, lab, size=13)
        lx += 30 + len(lab) * 7 + 26
    s.text(W - 20, 89, 'Path A = <linux/gpio.h> directly (kernel interface v2)   Path B = libgpiod 1.6 (kernel interface v1)',
           size=12.5, fill='#555', anchor='end')
    # phase headers
    y = 104
    for i, p in enumerate(PHASES):
        x = X0 + LW + GAP + i * (CW + GAP)
        s.raw(f'<rect x="{x}" y="{y}" width="{CW}" height="34" rx="8" fill="#333"/>')
        s.text(x + CW / 2, y + 22, p, size=14, weight='bold', fill='#fff', anchor='middle')
    y += 34 + GAP + 4
    for r in rows:
        if r is None:
            s.raw(f'<line x1="{X0}" y1="{y+14}" x2="{W-20}" y2="{y+14}" stroke="#d14a4a" stroke-width="3" stroke-dasharray="10,6"/>')
            s.raw(f'<rect x="{W/2-310}" y="{y+3}" width="620" height="22" fill="#fff"/>')
            s.text(W / 2, y + 19, 'SYSTEM CALL: the CPU switches from user space into the kernel (ARM "svc #0")',
                   size=13, weight='bold', fill='#d14a4a', anchor='middle')
            y += 34
            continue
        col, label, cells = r
        h = row_h(cells)
        f, st, t = C[col]
        s.raw(f'<rect x="{X0}" y="{y}" width="{LW}" height="{h}" rx="8" fill="{f}" stroke="{st}" stroke-width="2"/>')
        ly = y + 22
        for ln in label.split('\n'):
            s.text(X0 + 10, ly, ln, size=13, weight='bold', fill=t)
            ly += 17
        for i, cell in enumerate(cells):
            x = X0 + LW + GAP + i * (CW + GAP)
            empty = cell == ['—'] or (len(cell) <= 2 and cell[0].startswith('(') )
            s.raw(f'<rect x="{x}" y="{y}" width="{CW}" height="{h}" rx="8" fill="{f}" stroke="{st}" stroke-width="1.5"'
                  + (' stroke-dasharray="5,4" fill-opacity="0.5"' if empty else '') + '/>')
            cy = y + 20
            for ln in cell:
                s.text(x + 10, cy, ln, size=11.8, mono=True)
                cy += LH
        y += h + GAP
    y += 10
    for n in notes:
        s.rich(X0, y, n, size=13)
        y += 20
    s.save(f'{OUT}/{fname}')

# ---------------- C ----------------
C_ROWS = [
    ('green', 'Your code\nPath A\ngpio-blink-uapi.c', [
        ['find_line("[usr3 led]"):', ' for N = 0..31:', '  open("/dev/gpiochipN")', '  ioctl(fd, GPIO_GET_CHIPINFO_IOCTL)', '  for each line:', '   ioctl(fd, GPIO_V2_GET_LINEINFO_IOCTL)', '   strcmp(info.name, name)'],
        ['struct gpio_v2_line_request req;', 'memset(&req, 0, sizeof req);', 'offsets[0]=24  num_lines=1', 'flags = GPIO_V2_LINE_FLAG_OUTPUT', 'attr OUTPUT_VALUES = 0', 'ioctl(chip, GPIO_V2_GET_LINE_IOCTL)', '→ req.fd = line handle; close(chip)'],
        ['struct gpio_v2_line_values', '  v = { .mask=1, .bits=1 };', 'ioctl(req.fd,', '  GPIO_V2_LINE_SET_VALUES_IOCTL)', 'nanosleep(500 ms)', '… same with bits=0 …'],
        ['close(req.fd);', '(the kernel also closes it if', ' the program exits or is killed)'],
    ]),
    ('green', 'Your code\nPath B\ngpio-blink-gpiod.c', [
        ['line = gpiod_line_find(', '        "[usr3 led]");'],
        ['gpiod_line_request_output(line,', '    "gpio-blink-gpiod", 0);'],
        ['gpiod_line_set_value(line, 1);', 'usleep(500000);', 'gpiod_line_set_value(line, 0);'],
        ['gpiod_line_release(line);', 'gpiod_line_close_chip(line);'],
    ]),
    ('blue', 'libgpiod 1.6\n(Path B only;\nbuilt into the\nprogram)', [
        ['gpiod_chip_iter_new():', ' scandir("/dev") for gpiochip*', ' check /sys/bus/gpio/devices/…', 'gpiod_chip_open() →', ' open() + GPIO_GET_CHIPINFO_IOCTL', 'gpiod_chip_find_line() →', ' GPIO_GET_LINEINFO_IOCTL (v1)'],
        ['gpiod_line_request() fills', ' struct gpiohandle_request (v1)', 'ioctl(chip, GPIO_GET_LINEHANDLE_IOCTL)', '→ line handle fd, kept in line'],
        ['gpiod_line_set_value_bulk():', ' struct gpiohandle_data', 'ioctl(handle,', '  GPIOHANDLE_SET_LINE_VALUES_IOCTL)'],
        ['close(handle fd)', 'close(chip fd)'],
    ]),
    ('blue', 'glibc\n(C library)', [
        ['open() → syscall openat (#322)', 'ioctl() → syscall ioctl (#54)', 'codes: CHIPINFO 0x8044B401', ' V2_LINEINFO 0xC100B405 (A)', ' LINEINFO   0xC048B402 (B)'],
        ['ioctl() → syscall #54', 'codes: V2_GET_LINE    0xC250B407', '       GET_LINEHANDLE 0xC16CB403'],
        ['ioctl() → syscall #54', 'codes: V2_SET_VALUES  0xC010B40F', '       SET_LINE_VALUES 0xC040B409', 'sleeping: clock_nanosleep (not GPIO)'],
        ['close() → syscall close (#6)'],
    ]),
]
C_NOTES = [
    [('Both paths meet at the system call: ', False, True), ('Path A speaks the kernel\'s v2 interface, libgpiod 1.6 the older v1; below that, everything is identical.', False, False)],
    [('Only phase 4 turns the pin back into an input. ', False, True), ('Holding the line handle open (phases 2→4) is what makes toggling glitch-free.', False, False)],
    [('Errors: ', False, True), ('a failing system call returns -1 and sets ', False, False), ('errno', True, False), (' (e.g. EBUSY if someone else owns the line); C code checks every return value.', False, False)],
]

# ---------------- C++ ----------------
CPP_ROWS = [
    ('green', 'Your code\nPath A\ngpio-blink-uapi.cpp', [
        ['find_line(name) returns', '  std::optional<FoundLine>:', ' Fd chip(::open(path));', ' gpiochip_info info{};', ' ::ioctl(GPIO_GET_CHIPINFO_IOCTL)', ' gpio_v2_line_info line{};', ' ::ioctl(GPIO_V2_GET_LINEINFO_IOCTL)', ' match → {std::move(chip), path, i}'],
        ['request_output(*found, 0):', ' gpio_v2_line_request req{};', ' (fields as in C)', ' ::ioctl(GPIO_V2_GET_LINE_IOCTL)', '  fail → throw std::system_error', ' return Fd(req.fd);', 'found.reset(); // closes the chip'],
        ['set_value(line, 1):', ' gpio_v2_line_values v{};', ' ::ioctl(GPIO_V2_LINE_SET_VALUES_IOCTL)', '  fail → throw std::system_error', 'std::this_thread::sleep_for(half);'],
        ['end of scope: ~Fd() → ::close(fd)', 'also runs during exception', 'unwinding: no path leaks it'],
    ]),
    ('green', 'Your code\nPath B\ngpio-blink-gpiod.cpp', [
        ['gpiod::line line =', '  gpiod::find_line(name);', 'if (!line) …   // not found'],
        ['line.request({"gpio-blink-gpiod-cpp",', '  gpiod::line_request::', '    DIRECTION_OUTPUT, 0}, 0);'],
        ['line.set_value(1);', 'std::this_thread::sleep_for(half);', 'line.set_value(0);'],
        ['line.release();', 'then ~line(): last copy of its', 'chip → chip closed automatically'],
    ]),
    ('blue', 'C++ helpers\nA: libstdc++ +\nour Fd class\nB: libgpiodcxx\n(gpiod.hpp)', [
        ['A: Fd destructor closes chips', '   that weren\'t returned', 'B: make_chip_iter() →', '   chip::find_line() →', '   ::gpiod_chip_find_line()', '   wrapped in gpiod::line', '   (holds shared_ptr<gpiod_chip>)'],
        ['A: throw_errno() builds', '   std::system_error(errno, …)', 'B: line::request() →', '   line_bulk({*this}).request() →', '   ::gpiod_line_request_bulk()', '   -1 → throw std::system_error'],
        ['A: std::chrono durations;', '   sleep_for retries on EINTR', 'B: line::set_value() → temporary', '   line_bulk (heap alloc per call)', '   → ::gpiod_line_set_value_bulk()'],
        ['B: line_bulk::release() →', '   ::gpiod_line_release_bulk()', 'shared_ptr count → 0 →', '   ::gpiod_chip_close()'],
    ]),
    ('blue', 'libgpiod 1.6 C\n(Path B only;\nunder gpiod.hpp)', [
        ['as in the C diagram:', ' scandir("/dev"), sysfs check,', ' open() + GPIO_GET_CHIPINFO_IOCTL,', ' GPIO_GET_LINEINFO_IOCTL (v1)'],
        ['struct gpiohandle_request (v1)', 'ioctl(chip, GPIO_GET_LINEHANDLE_IOCTL)'],
        ['struct gpiohandle_data', 'ioctl(handle,', '  GPIOHANDLE_SET_LINE_VALUES_IOCTL)'],
        ['close(handle fd)', 'close(chip fd)'],
    ]),
    ('blue', 'glibc\n(C library)', [
        ['open() → openat (#322)', 'ioctl() → ioctl (#54)'],
        ['ioctl() → #54', ' V2_GET_LINE 0xC250B407 (A)', ' GET_LINEHANDLE 0xC16CB403 (B)'],
        ['ioctl() → #54', ' V2_SET_VALUES 0xC010B40F (A)', ' SET_LINE_VALUES 0xC040B409 (B)'],
        ['close() → close (#6)'],
    ]),
]
CPP_NOTES = [
    [('Same system calls, same kernel path as C: ', False, True), ('C++ changes only the user-space layers (ownership, errors, types).', False, False)],
    [('Errors: ', False, True), ('-1/errno from the kernel becomes ', False, False), ('std::system_error', True, False), ('; while it propagates, destructors run (', False, False), ('~Fd', True, False), (', ', False, False), ('~line', True, False), (') and close the fds, so the line is released.', False, False)],
    [('Cost of Path B: ', False, True), ('each ', False, False), ('line.set_value()', True, False), (' builds a temporary line_bulk (one heap allocation); fine for an LED, noticeable in tight loops.', False, False)],
]

draw('GPIO toggle in C: every layer', 'What gpio-blink-uapi.c (Path A) and gpio-blink-gpiod.c (Path B) do at each layer, down to the USR3 LED on our BeagleBone',
     C_ROWS, C_NOTES, 'gpio-toggle-c-layers.svg')
draw('GPIO toggle in C++: every layer', 'What gpio-blink-uapi.cpp (Path A) and gpio-blink-gpiod.cpp (Path B) do at each layer, down to the USR3 LED on our BeagleBone',
     CPP_ROWS, CPP_NOTES, 'gpio-toggle-cpp-layers.svg')
