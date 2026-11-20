// SPDX-License-Identifier: Apache-2.0
//! gpio-blink-gpiocdev-rs: blink a GPIO line using the `gpiocdev` crate,
//! a GPIO library written in Rust that talks to the kernel's GPIO interface.
//!
//! The line is requested once and held until the program ends, so it never
//! falls back to an input between "on" and "off".
//!
//! Usage: gpio-blink-gpiocdev-rs [LINE-NAME] [COUNT] [HALF-PERIOD-MS]
//!   LINE-NAME       device-tree name of the line   (default "[usr3 led]")
//!   COUNT           how many times to blink        (default 5)
//!   HALF-PERIOD-MS  time on, and time off, in ms   (default 500)

use gpiocdev::line::Value;
use std::{env, thread, time::Duration};

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let name = args.get(1).map(String::as_str).unwrap_or("[usr3 led]");
    let count: u32 = args.get(2).map(|s| s.parse()).transpose()?.unwrap_or(5);
    let half = Duration::from_millis(args.get(3).map(|s| s.parse()).transpose()?.unwrap_or(500));

    // Search every /dev/gpiochipN for a line with this name.
    let found = gpiocdev::find_named_line(name)
        .ok_or_else(|| format!("no GPIO line named \"{name}\" found"))?;
    println!("found \"{name}\": {} line {}", found.chip.display(), found.info.offset);

    // Take the line as an output, owner "gpio-blink-gpiocdev-rs", starting low.
    let req = gpiocdev::Request::builder()
        .with_found_line(&found)
        .with_consumer("gpio-blink-gpiocdev-rs")
        .as_output(Value::Inactive)
        .request()?;

    for _ in 0..count {
        req.set_lone_value(Value::Active)?; // high (`?` = on error, return it)
        thread::sleep(half);
        req.set_lone_value(Value::Inactive)?; // low
        thread::sleep(half);
    }

    drop(req); // release the line now (on this chip it becomes an input)
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
