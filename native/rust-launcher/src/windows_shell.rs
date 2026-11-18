// SPDX-License-Identifier: MIT
//! Unicode Windows Known Folders and ShellLink COM; no PowerShell/WSH subprocess.
use smartboard_launcher::{LaunchError, Result, promote_install, sha256};
use std::{fs, os::windows::ffi::OsStrExt, path::{Path, PathBuf}};
use windows::{
    core::{GUID, Interface, PCWSTR, w},
    Win32::{
        System::Com::{CoCreateInstance, CoInitializeEx, CoTaskMemFree, CoUninitialize, CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED, IPersistFile},
        UI::Shell::{FOLDERID_Desktop, FOLDERID_LocalAppData, FOLDERID_ProgramFiles, FOLDERID_Programs, FOLDERID_System, IShellLinkW, KF_FLAG_DEFAULT, SHGetKnownFolderPath, ShellLink},
    },
};

#[derive(Clone)]
pub struct Folders {
    pub data: PathBuf,
    pub programs: PathBuf,
    pub desktop: PathBuf,
    pub start_menu: PathBuf,
    pub stock: PathBuf,
    pub system: PathBuf,
}

fn known_folder(id: &GUID) -> Result<PathBuf> {
    unsafe {
        let path = SHGetKnownFolderPath(id, KF_FLAG_DEFAULT, None).map_err(|e| e.to_string())?;
        let value = path.to_string().map(PathBuf::from).map_err(|e| e.to_string());
        CoTaskMemFree(Some(path.0.cast()));
        Ok(value?)
    }
}

impl Folders {
    pub fn discover() -> Result<Self> {
        let local = known_folder(&FOLDERID_LocalAppData)?;
        Ok(Self {
            data: local.join("SmartBoardDimension"),
            programs: local.join("Programs/SmartBoardDimension"),
            desktop: known_folder(&FOLDERID_Desktop)?,
            start_menu: known_folder(&FOLDERID_Programs)?.join("SmartBoardDimension"),
            stock: known_folder(&FOLDERID_ProgramFiles)?.join("KiCad/10.0/share/kicad"),
            system: known_folder(&FOLDERID_System)?,
        })
    }
}

fn wide(path: &Path) -> Vec<u16> { path.as_os_str().encode_wide().chain(Some(0)).collect() }

struct ComApartment;
impl Drop for ComApartment { fn drop(&mut self) { unsafe { CoUninitialize(); } } }

pub fn shortcuts(folders: &Folders, executable: &Path, icon: &Path) -> Result<()> {
    // Called on a dedicated worker thread, not the file-dialog/GUI thread.
    unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok().map_err(|e| e.to_string())?; }
    let _apartment = ComApartment;
    for folder in [&folders.desktop, &folders.start_menu] {
        fs::create_dir_all(folder).map_err(|e| e.to_string())?;
        let destination = folder.join("スマート基板寸法（ネイティブ版）.lnk");
        let target = wide(executable);
        let working = wide(executable.parent().ok_or_else(|| LaunchError::new("Invalid launch path.", "起動先のパスが不正です。"))?);
        let icon = wide(icon);
        let destination = wide(&destination);
        unsafe {
            let link: IShellLinkW = CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER).map_err(|e| e.to_string())?;
            link.SetPath(PCWSTR(target.as_ptr())).map_err(|e| e.to_string())?;
            link.SetWorkingDirectory(PCWSTR(working.as_ptr())).map_err(|e| e.to_string())?;
            link.SetDescription(w!("SmartBoardDimension / スマート基板寸法")).map_err(|e| e.to_string())?;
            link.SetIconLocation(PCWSTR(icon.as_ptr()), 0).map_err(|e| e.to_string())?;
            let file: IPersistFile = link.cast().map_err(|e| e.to_string())?;
            file.Save(PCWSTR(destination.as_ptr()), true).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

pub fn persist_launcher(executable: &Path, folders: &Folders) -> Result<PathBuf> {
    let digest = sha256(executable)?;
    let folder = folders.programs.join(format!("registered-rust-{}", &digest[..12]));
    let target = folder.join("SmartBoardDimension.exe");
    if target.is_file() && sha256(&target)? == digest { return Ok(target); }
    fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    let nonce = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_nanos();
    let stage = folder.join(format!(".launcher-{}-{nonce}.tmp", std::process::id()));
    // create_new prevents accidentally replacing another running registration's staging file.
    let mut destination = fs::OpenOptions::new().write(true).create_new(true).open(&stage).map_err(|e| e.to_string())?;
    std::io::copy(&mut fs::File::open(executable).map_err(|e| e.to_string())?, &mut destination).map_err(|e| e.to_string())?;
    drop(destination);
    if sha256(&stage)? != digest { return Err(LaunchError::new("Could not verify the launcher copy.", "起動用ファイルのコピーを検証できませんでした。")); }
    promote_install(&stage, &target)?;
    Ok(target)
}
