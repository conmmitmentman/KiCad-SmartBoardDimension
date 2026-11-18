// SPDX-License-Identifier: MIT
use smartboard_launcher::*;
use std::{fs, path::{Path, PathBuf}};
use tempfile::TempDir;

const REQUIRED: [&str; 5] = ["SmartBoardDimension.exe", "bin/pcbnew.exe", "bin/_pcbnew.dll", "python/python.exe", "share/kicad/internat/ja/kicad.mo"];

fn write(path: &Path, bytes: &[u8]) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, bytes).unwrap();
}

fn package(root: &Path) {
    let mut manifest = String::new();
    for name in REQUIRED {
        let path = root.join(name);
        write(&path, b"artificial test fixture; not an executable");
        manifest.push_str(&format!("{}  {}\n", sha256(&path).unwrap(), name));
    }
    fs::write(root.join("manifest.sha256"), manifest).unwrap();
}

#[test]
fn malformed_and_traversing_manifests_are_rejected() {
    let digest = "a".repeat(64);
    for name in ["../outside", "/absolute", "C:\\outside", "safe/../../outside", "bin/app:stream", "CON", "bin/../escape", "bin//file", "bin/trailing.", "manifest.sha256"] {
        assert!(parse_manifest(&format!("{digest}  {name}\n")).is_err(), "accepted {name}");
    }
    assert!(parse_manifest("").is_err());
    assert!(parse_manifest("not a checksum").is_err());
    assert!(parse_manifest(&format!("{digest}  app.exe\n{digest}  APP.EXE\n")).is_err());
    assert!(parse_manifest(&format!("{digest}  日本語 と spaces/file.txt\n")).is_ok());
}

#[test]
fn bad_download_never_creates_an_installation() {
    let temp = TempDir::new().unwrap();
    let source = temp.path().join("source");
    package(&source);
    fs::write(source.join("bin/pcbnew.exe"), b"corrupted").unwrap();
    let target = temp.path().join("install");
    assert!(install_payload(&source, &target).is_err());
    assert!(!target.exists());
}

#[test]
fn install_reuse_repair_and_preserve_previous_files() {
    let temp = TempDir::new().unwrap();
    let source = temp.path().join("source");
    let parent = temp.path().join("install");
    package(&source);
    write(&source.join("unlisted.exe"), b"must not be installed");
    let installed = install_payload(&source, &parent).unwrap();
    assert!(!installed.join("unlisted.exe").exists());
    assert_eq!(install_payload(&source, &parent).unwrap(), installed);
    assert_eq!(fs::read_dir(&parent).unwrap().count(), 1);
    write(&installed.join("bin/pcbnew.exe"), b"damaged");
    write(&installed.join("user-notes.txt"), b"keep this");
    assert_eq!(install_payload(&source, &parent).unwrap(), installed);
    verify_payload(&installed).unwrap();
    let backup = fs::read_dir(&parent).unwrap().map(|e| e.unwrap().path()).find(|p| p.to_string_lossy().contains(".before-repair-")).unwrap();
    assert_eq!(fs::read(backup.join("user-notes.txt")).unwrap(), b"keep this");
    assert_eq!(fs::read(backup.join("bin/pcbnew.exe")).unwrap(), b"damaged");
}

#[test]
fn promotion_failure_restores_previous_directory() {
    let temp = TempDir::new().unwrap();
    let target = temp.path().join("target");
    write(&target.join("unchanged.txt"), b"original");
    assert!(promote_install(&temp.path().join("missing-stage"), &target).is_err());
    assert_eq!(fs::read(target.join("unchanged.txt")).unwrap(), b"original");
    assert_eq!(fs::read_dir(temp.path()).unwrap().count(), 1);
}

#[test]
fn first_run_config_and_user_sample_are_preserved() {
    let temp = TempDir::new().unwrap();
    let config = temp.path().join("config");
    let stock = temp.path().join("stock");
    write(&stock.join("template/fp-lib-table"), b"(fp_lib_table (version 7))");
    prepare_config(&config, &stock, Path::new("test-pythonw.exe"), Language::Japanese).unwrap();
    let initial: serde_json::Value = serde_json::from_slice(&fs::read(config.join("kicad_common.json")).unwrap()).unwrap();
    assert_eq!(initial["system"]["language"], "日本語");
    assert_eq!(initial["api"]["interpreter_path"], "test-pythonw.exe");
    fs::write(config.join("kicad_common.json"), b"custom settings").unwrap();
    fs::write(config.join("fp-lib-table"), b"custom libraries").unwrap();
    prepare_config(&config, &stock, Path::new("new-python.exe"), Language::English).unwrap();
    assert_eq!(fs::read(config.join("kicad_common.json")).unwrap(), b"custom settings");
    assert_eq!(fs::read(config.join("fp-lib-table")).unwrap(), b"custom libraries");
    let sample = sample_from_bytes(b"original sample", temp.path()).unwrap();
    fs::write(&sample, b"user-edited board").unwrap();
    sample_from_bytes(b"new sample", temp.path()).unwrap();
    assert_eq!(fs::read(&sample).unwrap(), b"user-edited board");
}

fn fake_build(root: &Path) {
    for name in ["pcbnew/pcbnew.exe", "pcbnew/_pcbnew.dll", "vcpkg_installed/x64-windows/tools/python3/python.exe"] { write(&root.join(name), b"MZ-test"); }
}

fn marker_bytes() -> Vec<u8> {
    let mut bytes = vec![0; 4 * 65536];
    for (i, marker) in NATIVE_MARKERS.iter().enumerate() {
        let pattern: Vec<u8> = marker.encode_utf16().flat_map(u16::to_le_bytes).collect();
        let start = (i + 1) * 65536 - pattern.len() + 5;
        bytes[start..start + pattern.len()].copy_from_slice(&pattern);
    }
    bytes
}

#[test]
fn identify_actual_binary_with_markers_across_chunk_boundaries() {
    let temp = TempDir::new().unwrap();
    fake_build(temp.path());
    assert!(identify_build(temp.path()).is_err());
    write(&temp.path().join("pcbnew/not-a-binary.h"), &marker_bytes());
    assert!(identify_build(temp.path()).is_err());
    write(&temp.path().join("pcbnew/pcbnew.kiface"), &marker_bytes());
    let layout = identify_build(temp.path()).unwrap();
    assert_eq!(layout.root(), temp.path().canonicalize().unwrap());
}

#[test]
fn command_uses_unicode_argument_and_private_environment_without_execution() {
    let temp = TempDir::new().unwrap();
    let root = temp.path().join("artificial build");
    fake_build(&root);
    let board = temp.path().join("日本語 の基板.kicad_pcb");
    write(&board, b"test board");
    let original_path = std::env::var_os("PATH");
    let layout = Layout::Build(root.clone());
    let command = layout.command(Some(&board), &temp.path().join("data"), &temp.path().join("stock"), &temp.path().join("system"), Language::English).unwrap();
    assert_eq!(command.get_args().collect::<Vec<_>>(), vec![board.as_os_str()]);
    assert_eq!(command_environment(&command, "KICAD_RUN_FROM_BUILD_DIR").unwrap(), "1");
    assert_eq!(command_environment(&command, "PYTHONHOME").unwrap(), root.join("vcpkg_installed/x64-windows/tools/python3"));
    assert_eq!(std::env::var_os("PATH"), original_path);
    let config = temp.path().join("data/config/10.0/kicad_common.json");
    let settings: serde_json::Value = serde_json::from_slice(&fs::read(config).unwrap()).unwrap();
    assert_eq!(settings["system"]["language"], "English");
    let blank = layout.command(None, &temp.path().join("data"), &temp.path().join("stock"), &temp.path().join("system"), Language::English).unwrap();
    assert_eq!(blank.get_args().count(), 0);
}

#[test]
fn registration_update_keeps_valid_json_and_prior_record() {
    let temp = TempDir::new().unwrap();
    let config = temp.path().join("registration.json");
    save_registration(&config, &Layout::Build(PathBuf::from("first"))).unwrap();
    save_registration(&config, &Layout::Build(PathBuf::from("second"))).unwrap();
    assert_eq!(load_registration(&config).unwrap().root(), Path::new("second"));
    assert_eq!(fs::read_dir(temp.path()).unwrap().count(), 2);
}

#[cfg(unix)]
#[test]
fn manifest_cannot_follow_a_symbolic_link() {
    use std::os::unix::fs::symlink;
    let temp = TempDir::new().unwrap();
    let source = temp.path().join("source");
    package(&source);
    let external = temp.path().join("outside.txt");
    write(&external, b"artificial test fixture; not an executable");
    fs::remove_file(source.join("SmartBoardDimension.exe")).unwrap();
    symlink(&external, source.join("SmartBoardDimension.exe")).unwrap();
    assert!(verify_payload(&source).is_err());
}

#[test]
fn language_selection_survives_restarts_and_can_switch_back() {
    let temp = TempDir::new().unwrap();
    let data = temp.path().join("launcher");
    assert_eq!(Language::load(&data), Language::Japanese);
    let changed = Language::load(&data).other();
    changed.save(&data).unwrap();
    assert_eq!(Language::load(&data), Language::English);
    Language::load(&data).other().save(&data).unwrap();
    assert_eq!(Language::load(&data), Language::Japanese);
    assert_eq!(fs::read_dir(data).unwrap().count(), 1);
}
