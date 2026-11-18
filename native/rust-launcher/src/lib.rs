// SPDX-License-Identifier: MIT
//! File operations and command construction are separate from the Windows UI.
//! Tests use artificial payloads; this module never discovers a real KiCad install.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    ffi::OsString,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};

mod language;
pub use language::{Language, LaunchError};

pub type Result<T> = std::result::Result<T, LaunchError>;
static SERIAL: AtomicU64 = AtomicU64::new(0);

fn unique_suffix() -> String {
    format!("{}-{}-{}", std::process::id(), SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos(), SERIAL.fetch_add(1, Ordering::Relaxed))
}

pub fn sha256(path: &Path) -> Result<String> {
    let mut file = File::open(path).map_err(|e| LaunchError::with_detail("Could not open the file", "ファイルを開けません", e))?;
    let mut hash = Sha256::new();
    let mut chunk = [0_u8; 65536];
    loop {
        let n = file.read(&mut chunk).map_err(|e| LaunchError::with_detail("Could not read the file", "読み取りに失敗しました", e))?;
        if n == 0 { break; }
        hash.update(&chunk[..n]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

#[derive(Debug, Clone)]
pub struct ManifestEntry {
    pub path: PathBuf,
    pub hash: String,
}

/// Parse the portable SHA256 format without permitting absolute paths, ADS, or traversal.
pub fn parse_manifest(text: &str) -> Result<Vec<ManifestEntry>> {
    let mut entries = Vec::new();
    let mut seen = HashSet::new();
    for line in text.trim_start_matches('\u{feff}').lines() {
        let bytes = line.as_bytes();
        if bytes.len() < 67 || bytes.get(64..66) != Some(b"  ") || !bytes[..64].iter().all(u8::is_ascii_hexdigit) {
            return Err(LaunchError::new("The package manifest is invalid. Extract the entire ZIP again.", "配布ファイル一覧の形式が不正です。ZIP全体を展開し直してください。"));
        }
        let name = &line[66..];
        let normalized = name.replace('\\', "/");
        let mut path = PathBuf::new();
        for part in normalized.split('/') {
            let stem = part.split('.').next().unwrap_or("").to_ascii_uppercase();
            let reserved = matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
                || (stem.len() == 4 && (stem.starts_with("COM") || stem.starts_with("LPT")) && matches!(stem.as_bytes()[3], b'1'..=b'9'));
            if part.is_empty() || part == "." || part == ".." || part.ends_with([' ', '.']) || reserved
                || part.chars().any(|c| c.is_control() || ":*?\"<>|".contains(c)) {
                return Err(LaunchError::new("A package file path is invalid.", "配布ファイルのパスが不正です。"));
            }
            path.push(part);
        }
        if normalized.eq_ignore_ascii_case("manifest.sha256") || !seen.insert(normalized.to_lowercase()) {
            return Err(LaunchError::new("The package manifest contains a duplicate or refers to itself.", "配布ファイル一覧に重複または自己参照があります。"));
        }
        entries.push(ManifestEntry { path, hash: line[..64].to_ascii_lowercase() });
    }
    if entries.is_empty() { return Err(LaunchError::new("The package manifest is empty.", "配布ファイル一覧が空です。")); }
    Ok(entries)
}

fn reject_link(path: &Path) -> Result<()> {
    let meta = fs::symlink_metadata(path).map_err(|e| LaunchError::with_detail("Could not check the package file", "配布ファイルを確認できません", e))?;
    #[cfg(windows)]
    let is_link = {
        use std::os::windows::fs::MetadataExt;
        meta.file_attributes() & 0x400 != 0
    };
    #[cfg(not(windows))]
    let is_link = meta.file_type().is_symlink();
    if is_link { return Err(LaunchError::new("The package contains a link. Extract the ZIP to a regular folder.", "配布フォルダー内のリンクは使用できません。ZIPを通常のフォルダーへ展開してください。")); }
    Ok(())
}

fn payload_path(root: &Path, relative: &Path) -> Result<PathBuf> {
    reject_link(root)?;
    let mut path = root.to_path_buf();
    for part in relative.components() {
        path.push(part);
        reject_link(&path)?;
    }
    if !path.is_file() { return Err(LaunchError::with_detail("Package file not found", "配布ファイルが見つかりません", relative.display())); }
    Ok(path)
}

pub fn verify_payload(root: &Path) -> Result<Vec<ManifestEntry>> {
    let manifest = payload_path(root, Path::new("manifest.sha256"))?;
    let text = fs::read_to_string(manifest).map_err(|e| LaunchError::with_detail("Could not read the package manifest", "配布一覧を読み取れません", e))?;
    let entries = parse_manifest(&text)?;
    for entry in &entries {
        if sha256(&payload_path(root, &entry.path)?)? != entry.hash {
            return Err(LaunchError::with_detail("File verification failed. Extract the entire ZIP again", "ファイルの検証に失敗しました。ZIP全体を展開し直してください", entry.path.display()));
        }
    }
    Ok(entries)
}

/// Promote only a fully staged package. Keep damaged installations for recovery.
pub fn promote_install(stage: &Path, target: &Path) -> Result<Option<PathBuf>> {
    let backup = if target.exists() {
        let backup = target.with_file_name(format!("{}.before-repair-{}", target.file_name().unwrap_or_default().to_string_lossy(), unique_suffix()));
        fs::rename(target, &backup).map_err(|e| LaunchError::with_detail("Could not prepare the repair. Close the PCB editor and launcher, then try again", "修復の準備ができません。PCBエディタと起動画面を閉じて再実行してください", e))?;
        Some(backup)
    } else { None };
    if let Err(error) = fs::rename(stage, target) {
        if let Some(previous) = &backup {
            if let Err(restore) = fs::rename(previous, target) {
                return Err(LaunchError::new(
                    format!("Replacement failed. The previous files are in {}. Recovery error: {restore}; {error}", previous.display()),
                    format!("交換に失敗しました。以前のファイルは {} に保管されています。復元エラー: {restore}; {error}", previous.display()),
                ));
            }
        }
        return Err(LaunchError::with_detail("Installation failed. The previous files were kept", "インストールできませんでした。以前のファイルは保持されています", error));
    }
    Ok(backup)
}

pub fn install_payload(source: &Path, parent: &Path) -> Result<PathBuf> {
    // Source verification must finish before creating anything at the destination.
    let entries = verify_payload(source)?;
    for required in ["SmartBoardDimension.exe", "bin/pcbnew.exe", "bin/_pcbnew.dll", "python/python.exe", "share/kicad/internat/ja/kicad.mo"] {
        if !entries.iter().any(|e| e.path == Path::new(required)) {
            return Err(LaunchError::with_detail("Required file is missing from the manifest", "配布ファイル一覧に必要な本体がありません", required));
        }
    }
    let manifest = source.join("manifest.sha256");
    let digest = sha256(&manifest)?;
    let target = parent.join(format!("native-rust-{}-{}", env!("CARGO_PKG_VERSION"), &digest[..12]));
    if target.is_dir() && verify_payload(&target).is_ok() && sha256(&target.join("manifest.sha256"))? == digest {
        return Ok(target);
    }
    fs::create_dir_all(parent).map_err(|e| LaunchError::with_detail("Could not create the installation folder", "導入先を作成できません", e))?;
    let stage = parent.join(format!(".staging-{}", unique_suffix()));
    fs::create_dir(&stage).map_err(|e| LaunchError::with_detail("Could not create the working folder", "作業フォルダーを作成できません", e))?;
    // Copy only enumerated files, so unverified extras cannot enter the installation.
    for entry in entries {
        let destination = stage.join(&entry.path);
        fs::create_dir_all(destination.parent().unwrap()).map_err(|e| LaunchError::with_detail("Could not create the installation folder", "導入先を作成できません", e))?;
        fs::copy(payload_path(source, &entry.path)?, destination).map_err(|e| LaunchError::with_detail("Could not copy the file", "コピーに失敗しました", e))?;
    }
    fs::copy(manifest, stage.join("manifest.sha256")).map_err(|e| LaunchError::with_detail("Could not copy the package manifest", "配布一覧をコピーできません", e))?;
    verify_payload(&stage)?;
    if sha256(&stage.join("manifest.sha256"))? != digest { return Err(LaunchError::new("The package changed while copying. Try again.", "コピー中に配布内容が変わりました。もう一度実行してください。")); }
    promote_install(&stage, &target)?;
    Ok(target)
}

fn write_new(path: &Path, bytes: &[u8]) -> Result<()> {
    match OpenOptions::new().write(true).create_new(true).open(path) {
        Ok(mut file) => file.write_all(bytes).map_err(|e| LaunchError::with_detail("Could not write the initial settings", "初期設定を書き込めません", e)),
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => Ok(()),
        Err(e) => Err(LaunchError::with_detail("Could not create the initial settings", "初期設定を作成できません", e)),
    }
}

pub fn prepare_config(config: &Path, stock: &Path, python: &Path, language: Language) -> Result<()> {
    fs::create_dir_all(config).map_err(|e| LaunchError::with_detail("Could not create the settings folder", "設定フォルダーを作成できません", e))?;
    let initial = serde_json::json!({"system":{"language":language.text("English", "日本語")},"api":{"interpreter_path":python}});
    write_new(&config.join("kicad_common.json"), &serde_json::to_vec_pretty(&initial).map_err(|e| e.to_string())?)?;
    for table in ["fp-lib-table", "sym-lib-table", "design-block-lib-table"] {
        let target = config.join(table);
        if target.exists() { continue; }
        let original = stock.join("template").join(table);
        let bytes = if original.is_file() { fs::read(original).map_err(|e| LaunchError::with_detail("Could not read the default library table", "標準ライブラリ一覧を読み取れません", e))? }
            else { format!("({} (version 7))\n", table.replace('-', "_")).into_bytes() };
        write_new(&target, &bytes)?;
    }
    Ok(())
}

pub fn sample_copy(source: &Path, user_data: &Path) -> Result<PathBuf> {
    let folder = user_data.join("samples");
    fs::create_dir_all(&folder).map_err(|e| LaunchError::with_detail("Could not create the sample folder", "サンプル保存先を作成できません", e))?;
    let destination = folder.join("circle.kicad_pcb");
    if !destination.exists() {
        write_new(&destination, &fs::read(source).map_err(|e| LaunchError::with_detail("Could not read the sample board", "サンプルが見つかりません", e))?)?;
    }
    Ok(destination)
}

pub fn sample_from_bytes(bytes: &[u8], user_data: &Path) -> Result<PathBuf> {
    let folder = user_data.join("samples");
    fs::create_dir_all(&folder).map_err(|e| LaunchError::with_detail("Could not create the sample folder", "サンプル保存先を作成できません", e))?;
    let destination = folder.join("circle.kicad_pcb");
    write_new(&destination, bytes)?;
    Ok(destination)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Layout { Packaged(PathBuf), Build(PathBuf) }

impl Layout {
    pub fn root(&self) -> &Path { match self { Self::Packaged(p) | Self::Build(p) => p } }
    pub fn editor(&self) -> PathBuf { self.root().join(if matches!(self, Self::Packaged(_)) { "bin/pcbnew.exe" } else { "pcbnew/pcbnew.exe" }) }
    pub fn python(&self) -> PathBuf { self.root().join(if matches!(self, Self::Packaged(_)) { "python" } else { "vcpkg_installed/x64-windows/tools/python3" }) }

    pub fn command(&self, board: Option<&Path>, user_data: &Path, stock: &Path, system: &Path, language: Language) -> Result<Command> {
        if !self.editor().is_file() || !self.python().join("python.exe").is_file() {
            return Err(LaunchError::new("The editor was not found. Reinstall it or register its build folder again.", "本体が見つかりません。導入またはビルド先の登録をやり直してください。"));
        }
        if let Self::Packaged(root) = self {
            if !root.join("bin/_pcbnew.dll").is_file() || !root.join("share/kicad/internat/ja/kicad.mo").is_file() {
                return Err(LaunchError::new("The editor or Japanese language files are missing. Reinstall the editor.", "本体または日本語ファイルがありません。インストールをやり直してください。"));
            }
        }
        if let Some(path) = board {
            if !path.is_file() { return Err(LaunchError::new("The selected board file was not found.", "開く基板ファイルが見つかりません。")); }
        }
        let config = user_data.join("config");
        let pythonw = self.python().join("pythonw.exe");
        let interpreter = if pythonw.is_file() { pythonw } else { self.python().join("python.exe") };
        prepare_config(&config.join("10.0"), stock, &interpreter, language)?;
        let mut command = Command::new(self.editor());
        if let Some(path) = board { command.arg(path); }
        command.current_dir(self.editor().parent().unwrap());
        command.env_remove("KICAD_RUN_FROM_BUILD_DIR");
        let mut search = Vec::new();
        match self {
            Self::Packaged(root) => {
                search.push(root.join("bin"));
                command.env("KICAD_STOCK_DATA_HOME", root.join("share/kicad"));
            }
            Self::Build(root) => {
                for relative in ["common", "common/gal", "api", "3d-viewer/3d_cache/sg", "vcpkg_installed/x64-windows/bin"] { search.push(root.join(relative)); }
                command.env("KICAD_RUN_FROM_BUILD_DIR", "1");
                command.env_remove("KICAD_STOCK_DATA_HOME");
            }
        }
        search.push(self.python()); search.push(system.to_path_buf());
        command.env("PATH", std::env::join_paths(search).map_err(|e| e.to_string())?);
        command.env("KICAD_CONFIG_HOME", config).env("KICAD_USE_EXTERNAL_PYTHONHOME", "1").env("PYTHONHOME", self.python());
        let binding = self.root().join(if matches!(self, Self::Packaged(_)) { "bin" } else { "pcbnew" });
        command.env("PYTHONPATH", std::env::join_paths([binding, self.python().join("Lib/site-packages")]).map_err(|e| e.to_string())?);
        for (variable, directory) in [("FOOTPRINT", "footprints"), ("SYMBOL", "symbols"), ("3DMODEL", "3dmodels"), ("TEMPLATE", "template")] {
            let path = stock.join(directory);
            if path.is_dir() { command.env(format!("KICAD10_{variable}_DIR"), path); }
        }
        Ok(command)
    }
}

pub const NATIVE_MARKERS: [&str; 3] = ["数値・計算式 → Enter確定 / Esc取消", "半径 (mm) · 中心固定", "寸法から基板外形を変更"];

pub fn contains_native_markers(path: &Path) -> Result<bool> {
    let patterns: Vec<Vec<u8>> = NATIVE_MARKERS.iter().map(|s| s.encode_utf16().flat_map(u16::to_le_bytes).collect()).collect();
    let overlap = patterns.iter().map(Vec::len).max().unwrap() - 1;
    let mut buffer = vec![0; 65536 + overlap];
    let mut carry = 0;
    let mut found = [false; 3];
    let mut file = File::open(path).map_err(|e| LaunchError::with_detail("Could not read the editor binary", "本体を読み取れません", e))?;
    loop {
        let n = file.read(&mut buffer[carry..carry + 65536]).map_err(|e| e.to_string())?;
        if n == 0 { return Ok(false); }
        let length = carry + n;
        for (i, pattern) in patterns.iter().enumerate() {
            if !found[i] { found[i] = buffer[..length].windows(pattern.len()).any(|s| s == pattern); }
        }
        if found.iter().all(|v| *v) { return Ok(true); }
        carry = overlap.min(length);
        buffer.copy_within(length - carry..length, 0);
    }
}

pub fn identify_build(root: &Path) -> Result<Layout> {
    for relative in ["pcbnew/pcbnew.exe", "pcbnew/_pcbnew.dll", "vcpkg_installed/x64-windows/tools/python3/python.exe"] {
        if !root.join(relative).is_file() { return Err(LaunchError::with_detail("Required build file not found", "ビルド済みファイルがありません", relative)); }
    }
    for file in fs::read_dir(root.join("pcbnew")).map_err(|e| e.to_string())? {
        let path = file.map_err(|e| e.to_string())?.path();
        let extension = path.extension().and_then(|s| s.to_str()).unwrap_or("");
        if path.is_file() && (extension.eq_ignore_ascii_case("dll") || extension.eq_ignore_ascii_case("kiface")) && contains_native_markers(&path)? {
            return Ok(Layout::Build(root.canonicalize().map_err(|e| e.to_string())?));
        }
    }
    Err(LaunchError::new("Native dimension editing was not found. Select a build folder with the source patch applied.", "寸法を数字から編集する機能が見つかりません。パッチを適用してビルドしたフォルダーを選んでください。"))
}

pub fn save_registration(path: &Path, layout: &Layout) -> Result<()> {
    let folder = path.parent().ok_or_else(|| LaunchError::new("Invalid settings path.", "設定先が不正です。"))?;
    fs::create_dir_all(folder).map_err(|e| e.to_string())?;
    let stage = folder.join(format!(".registration-{}", unique_suffix()));
    fs::write(&stage, serde_json::to_vec_pretty(layout).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    promote_install(&stage, path)?;
    Ok(())
}

pub fn load_registration(path: &Path) -> Result<Layout> {
    Ok(serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?)
}

pub fn command_environment(command: &Command, key: &str) -> Option<OsString> {
    command.get_envs().find(|(name, _)| *name == key).and_then(|(_, value)| value.map(OsString::from))
}
