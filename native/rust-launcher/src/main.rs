// SPDX-License-Identifier: MIT
#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg(windows)]
mod windows_shell;
#[cfg(windows)]
mod windows_ui;

#[cfg(windows)]
fn main() {
    if let Err(error) = windows_ui::run() {
        windows_ui::show_error(None, &error);
    }
}

#[cfg(not(windows))]
fn main() {
    eprintln!("The launcher UI is available on Windows.");
}
