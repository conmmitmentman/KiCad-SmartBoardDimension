// SPDX-License-Identifier: MIT
#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg(windows)]
mod windows_shell;
#[cfg(windows)]
mod windows_ui;

#[cfg(windows)]
fn main() {
    windows_ui::start();
}

#[cfg(not(windows))]
fn main() {
    eprintln!("The launcher UI is available on Windows.");
}
