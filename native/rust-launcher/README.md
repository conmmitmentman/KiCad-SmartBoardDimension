# Rust Windows launcher

This crate implements installation, manifest verification, native-build registration,
private KiCad configuration, process launching, a Japanese GUI, and persistent
Desktop/Start-menu shortcuts in Rust. It does not execute the legacy C# or
PowerShell implementation.

Build with Rust 1.88 or newer on Windows:

```text
cargo test -p smartboard-launcher
cargo build --release -p smartboard-launcher
```

The output is `target/release/smartboard-launcher.exe`. The Windows packager copies
it to `app/SmartBoardDimension.exe` and `Install.exe`. A root containing
`app/manifest.sha256` displays the installer; an executable beside `bin/pcbnew.exe`
displays the packaged launcher. A standalone executable can register an existing
native build and copies itself into the user's Programs folder. Registration uses
compiled UTF-16 feature strings as identification, not as a digital signature.

The installer verifies every listed source file before destination writes, copies
only listed files, verifies staging, and preserves a damaged prior installation in
a `.before-repair-*` directory. A failed promotion restores the prior directory.
Failed staging directories are retained for recovery. Settings and edited samples
live separately and are not replaced during installation or repair.

The launcher uses standard Win32 controls and the Windows file dialog. Windows
handles font rendering. When the PCB editor starts, the launcher exits.
The installer checks file contents in 64 KiB chunks. KiCad's Japanese catalogs
are still required in the packaged editor.

Direct dependencies are pinned: windows 0.62.2, sha2 0.10.9, serde 1.0.228,
and serde_json 1.0.145. The root Cargo.lock
records transitive versions. The GUI is Windows-only; file/command tests run on
Windows or Linux with synthetic fixtures and never launch KiCad.

API references used for implementation:
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createwindowexw
- https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ifileopendialog
- https://microsoft.github.io/windows-docs-rs/doc/windows/Win32/UI/Shell/struct.IShellLinkW.html
- https://microsoft.github.io/windows-docs-rs/doc/windows/Win32/UI/Shell/fn.SHGetKnownFolderPath.html
- https://docs.rs/sha2/0.10.9/sha2/

The Rust source alone is not a KiCad binary distribution. Packaging still needs a
verified native KiCad build, its dependencies/resources, corresponding sources,
and release validation. File-level unit tests do not establish real-PC GUI or
clean-PC installation success.
