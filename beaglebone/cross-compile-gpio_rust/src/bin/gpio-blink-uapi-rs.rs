// SPDX-License-Identifier: Apache-2.0
//! gpio-blink-uapi-rs: blink a GPIO line by calling the kernel's GPIO
//! interface (<linux/gpio.h>, "v2") directly, with no GPIO library.
//!
//! Rust has no <linux/gpio.h>, so the kernel's structures are re-declared
//! below with the same memory layout (`#[repr(C)]`). Calls into the kernel
//! go through the `libc` crate and are marked `unsafe`: the compiler can't
//! check what the kernel does with the memory we hand it.
//!
//! The line is requested once and held until the program ends, so it never
//! falls back to an input between "on" and "off".
//!
//! Usage: gpio-blink-uapi-rs [LINE-NAME] [COUNT] [HALF-PERIOD-MS]
//!   LINE-NAME       device-tree name of the line   (default "[usr3 led]")
//!   COUNT           how many times to blink        (default 5)
//!   HALF-PERIOD-MS  time on, and time off, in ms   (default 500)

use std::ffi::CString;
use std::io;
use std::os::fd::{FromRawFd, OwnedFd, AsRawFd};
use std::{env, mem, thread, time::Duration};

// ---- Copies of the kernel's structures from <linux/gpio.h> ----------------

const GPIO_MAX_NAME_SIZE: usize = 32;
const GPIO_V2_LINES_MAX: usize = 64;
const GPIO_V2_LINE_NUM_ATTRS_MAX: usize = 10;
const GPIO_V2_LINE_FLAG_OUTPUT: u64 = 1 << 3;
const GPIO_V2_LINE_ATTR_ID_OUTPUT_VALUES: u32 = 2;

#[repr(C)]
struct GpiochipInfo {
    name: [u8; GPIO_MAX_NAME_SIZE],
    label: [u8; GPIO_MAX_NAME_SIZE],
    lines: u32,
}

#[repr(C)]
#[derive(Clone, Copy)]
struct GpioV2LineAttribute {
    id: u32,
    padding: u32,
    value: u64, // a union in C (flags / values / debounce); we only use "values"
}

#[repr(C)]
#[derive(Clone, Copy)]
struct GpioV2LineConfigAttribute {
    attr: GpioV2LineAttribute,
    mask: u64,
}

#[repr(C)]
struct GpioV2LineConfig {
    flags: u64,
    num_attrs: u32,
    padding: [u32; 5],
    attrs: [GpioV2LineConfigAttribute; GPIO_V2_LINE_NUM_ATTRS_MAX],
}

#[repr(C)]
struct GpioV2LineRequest {
    offsets: [u32; GPIO_V2_LINES_MAX],
    consumer: [u8; GPIO_MAX_NAME_SIZE],
    config: GpioV2LineConfig,
    num_lines: u32,
    event_buffer_size: u32,
    padding: [u32; 5],
    fd: i32,
}

#[repr(C)]
struct GpioV2LineInfo {
    name: [u8; GPIO_MAX_NAME_SIZE],
    consumer: [u8; GPIO_MAX_NAME_SIZE],
    offset: u32,
    num_attrs: u32,
    flags: u64,
    attrs: [GpioV2LineAttribute; GPIO_V2_LINE_NUM_ATTRS_MAX],
    padding: [u32; 4],
}

#[repr(C)]
struct GpioV2LineValues {
    bits: u64,
    mask: u64,
}

// The compiler checks these sizes match the kernel's, so a typo in the
// structures above stops the build instead of confusing the kernel.
const _: () = assert!(mem::size_of::<GpiochipInfo>() == 68);
const _: () = assert!(mem::size_of::<GpioV2LineInfo>() == 256);
const _: () = assert!(mem::size_of::<GpioV2LineRequest>() == 592);
const _: () = assert!(mem::size_of::<GpioV2LineValues>() == 16);

// ioctl request codes, built the same way as the kernel's _IOR/_IOWR macros:
// direction (2 bits) | size (14 bits) | type 0xB4 = GPIO | command number.
const fn ioc(dir: u32, nr: u32, size: usize) -> u32 {
    (dir << 30) | ((size as u32) << 16) | (0xB4 << 8) | nr
}
const IOC_READ: u32 = 2;
const IOC_READ_WRITE: u32 = 3;
const GPIO_GET_CHIPINFO_IOCTL: u32 = ioc(IOC_READ, 0x01, mem::size_of::<GpiochipInfo>());
const GPIO_V2_GET_LINEINFO_IOCTL: u32 = ioc(IOC_READ_WRITE, 0x05, mem::size_of::<GpioV2LineInfo>());
const GPIO_V2_GET_LINE_IOCTL: u32 = ioc(IOC_READ_WRITE, 0x07, mem::size_of::<GpioV2LineRequest>());
const GPIO_V2_LINE_SET_VALUES_IOCTL: u32 = ioc(IOC_READ_WRITE, 0x0F, mem::size_of::<GpioV2LineValues>());

// ---- Small helpers ----------------------------------------------------------

/// A zero-filled structure (the kernel requires unused/padding fields = 0).
fn zeroed<T>() -> T {
    // SAFETY: only used for the plain-number structures above, for which
    // "all bytes zero" is a valid value.
    unsafe { mem::zeroed() }
}

/// Call ioctl() and turn -1 into a Rust error carrying errno's message.
fn ioctl<T>(fd: &OwnedFd, request: u32, arg: &mut T) -> io::Result<()> {
    // SAFETY: `arg` is a live, correctly sized #[repr(C)] structure matching
    // `request`, so the kernel reads and writes only memory we own.
    let rc = unsafe { libc::ioctl(fd.as_raw_fd(), request as _, arg as *mut T) };
    if rc < 0 { Err(io::Error::last_os_error()) } else { Ok(()) }
}

/// Text from a fixed-size, zero-terminated C string field.
fn c_text(bytes: &[u8]) -> &str {
    let end = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
    std::str::from_utf8(&bytes[..end]).unwrap_or("")
}

/// Open a file for reading and writing; the returned OwnedFd closes itself.
fn open_rw(path: &str) -> io::Result<OwnedFd> {
    let c_path = CString::new(path).expect("path has no zero bytes");
    // SAFETY: c_path is a valid zero-terminated string.
    let fd = unsafe { libc::open(c_path.as_ptr(), libc::O_RDWR | libc::O_CLOEXEC) };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: fd is a freshly opened descriptor that nothing else owns.
    Ok(unsafe { OwnedFd::from_raw_fd(fd) })
}

/// Search /dev/gpiochip0, 1, 2 ... for a line called `name`.
fn find_line(name: &str) -> Option<(OwnedFd, String, u32)> {
    for n in 0..32 {
        let path = format!("/dev/gpiochip{n}");
        let Ok(chip) = open_rw(&path) else { continue }; // no such chip: next
        let mut info: GpiochipInfo = zeroed();
        if ioctl(&chip, GPIO_GET_CHIPINFO_IOCTL, &mut info).is_err() {
            continue;
        }
        for offset in 0..info.lines {
            let mut line: GpioV2LineInfo = zeroed();
            line.offset = offset;
            if ioctl(&chip, GPIO_V2_GET_LINEINFO_IOCTL, &mut line).is_ok()
                && c_text(&line.name) == name
            {
                return Some((chip, path, offset));
            }
        }
    } // a chip that wasn't returned is closed automatically here
    None
}

fn set_value(line: &OwnedFd, value: bool) -> io::Result<()> {
    let mut vals = GpioV2LineValues { mask: 1, bits: value as u64 }; // line #0 of our request
    ioctl(line, GPIO_V2_LINE_SET_VALUES_IOCTL, &mut vals)
}

// ---- The program -----------------------------------------------------------

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let name = args.get(1).map(String::as_str).unwrap_or("[usr3 led]");
    let count: u32 = args.get(2).map(|s| s.parse()).transpose()?.unwrap_or(5);
    let half = Duration::from_millis(args.get(3).map(|s| s.parse()).transpose()?.unwrap_or(500));

    let (chip, path, offset) =
        find_line(name).ok_or_else(|| format!("no GPIO line named \"{name}\" found"))?;
    println!("found \"{name}\": {path} line {offset}");

    // Request the line as an output, starting low.
    let mut req: GpioV2LineRequest = zeroed();
    req.offsets[0] = offset; // which line on this chip
    req.num_lines = 1; // just that one
    let owner = b"gpio-blink-uapi-rs";
    req.consumer[..owner.len()].copy_from_slice(owner); // owner name (gpioinfo)
    req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT; // make it an output
    req.config.num_attrs = 1; // one extra setting:
    req.config.attrs[0].mask = 1; //   for line #0 ...
    req.config.attrs[0].attr.id = GPIO_V2_LINE_ATTR_ID_OUTPUT_VALUES;
    req.config.attrs[0].attr.value = 0; //   ... start low
    ioctl(&chip, GPIO_V2_GET_LINE_IOCTL, &mut req)
        .map_err(|e| format!("cannot request {path} line {offset}: {e}"))?;
    drop(chip); // the chip isn't needed any more; the line handle stays valid

    // SAFETY: the kernel just gave us this new descriptor; nothing else owns it.
    let line = unsafe { OwnedFd::from_raw_fd(req.fd) };

    for _ in 0..count {
        set_value(&line, true)?;
        thread::sleep(half);
        set_value(&line, false)?;
        thread::sleep(half);
    }

    drop(line); // close the handle: the line is released (becomes an input)
    println!("done");
    Ok(())
}

fn main() {
    // Print errors as plain messages ("error: ...") and exit with status 1.
    if let Err(e) = run() {
        eprintln!("error: {e}");
        std::process::exit(1);
    }
}
