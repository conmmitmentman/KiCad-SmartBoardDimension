# Build and register the Rust native edition on Windows

[日本語](RUST_MIGRATION_JA.md) · **English**

## Requirements

Use Windows x64, Rust 1.88 or later with the MSVC toolchain, Visual Studio 2022 with C++ support, and Python 3. Building the PCB Editor also requires the dependencies in the [KiCad Windows MSVC build guide](https://dev-docs.kicad.org/en/build/windows-msvc/), including CMake, Ninja, SWIG, and vcpkg.

Extract the source ZIP from the [latest release](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/releases/latest). Run the following commands from the extracted folder containing `Cargo.toml`.

## Build the launcher and test the Rust code

```powershell
cargo test --workspace --locked
cargo build --release -p smartboard-launcher --locked
```

The launcher output is `target\release\smartboard-launcher.exe`. The PCB Editor builds and links the separate Rust dimension library when you build KiCad.

## Build the PCB Editor

Use an unmodified checkout of the official KiCad `10.0.7` source. In Developer PowerShell, check that `cargo --version` works, then run these commands from the extracted source ZIP folder. Adjust the KiCad source path if needed.

```powershell
git clone --depth 1 --branch 10.0.7 https://github.com/KiCad/kicad-source-mirror.git C:\dev\kicad
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests --dry-run
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests
```

Follow the official MSVC build guide to prepare the dependencies and presets. From the KiCad source folder, configure and build. The preset names below are examples. The `i18n` target builds the standard KiCad translations, including Japanese.

```powershell
cmake --preset msvc-win64-release -DKICAD_BUILD_QA_TESTS=ON
cmake --build --preset win64-release --target pcbnew qa_pcbnew bitmap_archive_build i18n --parallel 4
```

## Register once, then use the shortcut

Open `smartboard-launcher.exe`, click **English**, and choose **Register or change build folder**. Select the build output folder that contains the `pcbnew` directory. Once registration finishes, the launcher creates a desktop and Start menu shortcut named **スマート基板寸法（ネイティブ版）**.

Use that shortcut next time. It remembers the launcher language and the build folder. The existing editor language setting, settings files, and edited sample are preserved. To switch the editor and native dimension messages, use **Preferences → Set Language** in the PCB Editor.

## Verification

Automated tests use synthetic boards and simulated setup to exercise the Rust engine, C++ bridge, and Windows launcher. The full KiCad build and on-canvas language switching are still unverified.

[Back to the English README](../README.en.md)
