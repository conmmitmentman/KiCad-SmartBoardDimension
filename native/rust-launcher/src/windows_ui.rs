// SPDX-License-Identifier: MIT
//! Small Windows launcher using OS controls and common dialogs.
use crate::windows_shell::{self, Folders};
use smartboard_launcher::{
    identify_build, install_payload, load_registration, sample_from_bytes, save_registration,
    Language, LaunchError, Layout, Result,
};
use std::{
    fs,
    os::windows::ffi::OsStringExt,
    path::{Path, PathBuf},
    sync::mpsc::{self, Receiver, TryRecvError},
    thread,
};
use windows::{
    core::{w, PCWSTR},
    Win32::{
        Foundation::{HINSTANCE, HWND, LPARAM, LRESULT, WPARAM},
        Graphics::Gdi::{GetStockObject, COLOR_WINDOW, DEFAULT_GUI_FONT, HBRUSH},
        System::{
            Com::{CoCreateInstance, CoInitializeEx, CoTaskMemFree, CoUninitialize, CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED},
            LibraryLoader::GetModuleHandleW,
        },
        UI::{Input::KeyboardAndMouse::EnableWindow, Shell::{
            Common::COMDLG_FILTERSPEC, FileOpenDialog, IFileOpenDialog, FOS_FILEMUSTEXIST,
            FOS_FORCEFILESYSTEM, FOS_PATHMUSTEXIST, FOS_PICKFOLDERS, SIGDN_FILESYSPATH,
        }, WindowsAndMessaging::*},
    },
};

const SAMPLE: &[u8] = include_bytes!("../../examples/circle.kicad_pcb");
const REGISTRATION: &str = "registered-build-rust.json";
const REGISTER: usize = 101;
const INSTALL: usize = 102;
const NEW: usize = 103;
const OPEN: usize = 104;
const EXAMPLE: usize = 105;
const LANGUAGE: usize = 106;
const TIMER: usize = 1;
const ACTION: u32 = WM_APP + 1;

struct App {
    executable: PathBuf,
    folders: Folders,
    layout: Option<Layout>,
    installer: bool,
    pending: Option<Receiver<Result<Layout>>>,
    language: Language,
    language_button: HWND,
    hint: HWND,
    status: HWND,
    buttons: [HWND; 5],
}

fn title(language: Language) -> PCWSTR {
    language.text(w!("SmartBoardDimension — Native"), w!("スマート基板寸法 — ネイティブ版"))
}

fn set_text(window: HWND, text: &str) {
    let wide: Vec<u16> = text.encode_utf16().chain(Some(0)).collect();
    unsafe { let _ = SetWindowTextW(window, PCWSTR(wide.as_ptr())); }
}

impl App {
    fn apply_language(&self, window: HWND) {
        let language = self.language;
        unsafe { let _ = SetWindowTextW(window, title(language)); }
        set_text(self.language_button, language.text("日本語", "English"));
        set_text(self.hint, language.text(
            "Click a PCB dimension value to enter a number or formula.",
            "PCBの寸法数字をクリックすると、数値や計算式で編集できます。",
        ));
        let labels = [
            language.text("Register or change build folder", "ネイティブ版のビルド先を登録／変更"),
            language.text("Install or repair", "インストール／修復"),
            language.text("New board", "新しい基板を作る"),
            language.text("Open board file", "基板ファイルを開く"),
            language.text("Try the circle example", "円のサンプルで試す"),
        ];
        for (&button, label) in self.buttons.iter().zip(labels) {
            set_text(button, label);
        }
        self.describe();
    }

    fn refresh_controls(&self) {
        unsafe {
            let _ = ShowWindow(self.language_button, SW_SHOW);
            let _ = EnableWindow(self.language_button, self.pending.is_none());
        }
        for (index, &button) in self.buttons.iter().enumerate() {
            let id = REGISTER + index;
            let visible = match id {
                INSTALL => self.installer,
                REGISTER => !self.installer && !matches!(self.layout, Some(Layout::Packaged(_))),
                _ => !self.installer,
            };
            let enabled = self.pending.is_none() && (index < 2 || self.layout.is_some());
            unsafe {
                let _ = ShowWindow(button, if visible { SW_SHOW } else { SW_HIDE });
                let _ = EnableWindow(button, enabled);
            }
        }
    }

    fn status(&self, value: &str) {
        set_text(self.status, value);
    }

    fn describe(&self) {
        let text = if self.installer {
            self.language.text("Installs for the current user. Administrator access is not required.", "このユーザー用にインストールします。管理者権限は不要です。").into()
        } else if let Some(layout) = &self.layout {
            format!("{}\r\n{}", self.language.text("Editor location", "使用する本体"), layout.root().display())
        } else {
            self.language.text("Register the build folder for the editor with native dimensions.", "初回は、寸法機能を組み込んだビルド先を登録してください。").into()
        };
        self.status(&text);
    }

    fn task(&mut self, window: HWND, action: impl FnOnce() -> Result<Layout> + Send + 'static) -> Result<()> {
        // The message loop is idle when nobody is installing or registering.
        if unsafe { SetTimer(Some(window), TIMER, 120, None) } == 0 {
            return Err(LaunchError::new("Could not start monitoring the operation.", "処理の監視を開始できません。"));
        }
        let (send, receive) = mpsc::channel();
        if let Err(error) = thread::Builder::new().spawn(move || { let _ = send.send(action()); }) {
            unsafe { let _ = KillTimer(Some(window), TIMER); }
            return Err(error.to_string().into());
        }
        self.pending = Some(receive);
        self.refresh_controls();
        self.status(self.language.text("Checking files. Keep this window open until the operation finishes.", "ファイルを確認しています。完了までこの画面を開いておいてください。"));
        Ok(())
    }

    fn finish_task(&mut self, window: HWND) {
        let Some(receiver) = &self.pending else { return };
        let result = match receiver.try_recv() {
            Ok(result) => result,
            Err(TryRecvError::Empty) => return,
            Err(TryRecvError::Disconnected) => Err(LaunchError::new("The operation was interrupted. Try again.", "処理が中断されました。もう一度実行してください。")),
        };
        self.pending = None;
        unsafe { let _ = KillTimer(Some(window), TIMER); }
        match result {
            Ok(layout) => {
                self.layout = Some(layout);
                self.installer = false;
                self.status(self.language.text("Setup complete. Use the shortcut to start next time.", "設定完了。次回から専用アイコンで起動できます。"));
            }
            Err(error) => {
                self.describe();
                show_error(Some(window), &error, self.language);
            }
        }
        self.refresh_controls();
    }

    // Return true only after starting the editor. The launcher then exits.
    fn launch(&self, board: Option<&Path>) -> Result<bool> {
        let layout = self.layout.as_ref().ok_or_else(|| LaunchError::new("Install the editor or register its build folder.", "本体をインストールするか、ビルド先を登録してください。"))?;
        layout.command(board, &self.folders.data, &self.folders.stock, &self.folders.system, self.language)?
            .spawn().map_err(|error| LaunchError::with_detail("Could not start the PCB editor", "PCBエディタを起動できません", error))?;
        Ok(true)
    }

    fn handle(&mut self, window: HWND, action: usize) -> Result<bool> {
        if self.pending.is_some() { return Ok(false); }
        match action {
            LANGUAGE => {
                let language = self.language.other();
                language.save(&self.folders.data)?;
                self.language = language;
                self.apply_language(window);
            }
            INSTALL if self.installer => {
                let source = self.executable.with_file_name("app");
                let folders = self.folders.clone();
                self.task(window, move || {
                    let target = install_payload(&source, &folders.programs)?;
                    windows_shell::shortcuts(&folders, &target.join("SmartBoardDimension.exe"), &target.join("bin/pcbnew.exe"))?;
                    fs::create_dir_all(&folders.data).map_err(|e| e.to_string())?;
                    fs::write(folders.data.join("installed-path.txt"), target.to_string_lossy().as_bytes()).map_err(|e| e.to_string())?;
                    Ok(Layout::Packaged(target))
                })?;
            }
            REGISTER if !self.installer && !matches!(self.layout, Some(Layout::Packaged(_))) => {
                if let Some(root) = pick_path(window, true, self.language)? {
                    let executable = self.executable.clone();
                    let folders = self.folders.clone();
                    self.task(window, move || {
                        let layout = identify_build(&root)?;
                        let persistent = windows_shell::persist_launcher(&executable, &folders)?;
                        save_registration(&folders.data.join(REGISTRATION), &layout)?;
                        windows_shell::shortcuts(&folders, &persistent, &layout.editor())?;
                        Ok(layout)
                    })?;
                }
            }
            NEW if !self.installer => return self.launch(None),
            OPEN if !self.installer => {
                if let Some(board) = pick_path(window, false, self.language)? { return self.launch(Some(&board)); }
            }
            EXAMPLE if !self.installer => {
                let board = sample_from_bytes(SAMPLE, &self.folders.data)?;
                return self.launch(Some(&board));
            }
            _ => {}
        }
        Ok(false)
    }
}

fn pick_path(window: HWND, folder: bool, language: Language) -> Result<Option<PathBuf>> {
    unsafe {
        let dialog: IFileOpenDialog = CoCreateInstance(&FileOpenDialog, None, CLSCTX_INPROC_SERVER)
            .map_err(|e| e.to_string())?;
        let common = FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST;
        dialog.SetOptions(common | if folder { FOS_PICKFOLDERS } else { FOS_FILEMUSTEXIST })
            .map_err(|e| e.to_string())?;
        if folder {
            dialog.SetTitle(language.text(w!("Select the build folder that contains pcbnew"), w!("pcbnewフォルダーが入っているビルド先を選択"))).map_err(|e| e.to_string())?;
        } else {
            dialog.SetTitle(language.text(w!("Open KiCad board"), w!("KiCad基板を開く"))).map_err(|e| e.to_string())?;
            dialog.SetFileTypes(&[COMDLG_FILTERSPEC { pszName: language.text(w!("KiCad board"), w!("KiCad基板")), pszSpec: w!("*.kicad_pcb") }])
                .map_err(|e| e.to_string())?;
        }
        if let Err(error) = dialog.Show(Some(window)) {
            return if error.code().0 as u32 == 0x8007_04C7 { Ok(None) } else { Err(error.to_string().into()) };
        }
        let item = dialog.GetResult().map_err(|e| e.to_string())?;
        let path = item.GetDisplayName(SIGDN_FILESYSPATH).map_err(|e| e.to_string())?;
        let result = PathBuf::from(std::ffi::OsString::from_wide(path.as_wide()));
        CoTaskMemFree(Some(path.0.cast()));
        Ok(Some(result))
    }
}

fn show_error(owner: Option<HWND>, error: &LaunchError, language: Language) {
    let text: Vec<u16> = error.message(language).encode_utf16().chain(Some(0)).collect();
    unsafe { MessageBoxW(owner, PCWSTR(text.as_ptr()), title(language), MB_OK | MB_ICONERROR); }
}

unsafe extern "system" fn window_proc(window: HWND, message: u32, w: WPARAM, l: LPARAM) -> LRESULT {
    match message {
        WM_COMMAND if l.0 != 0 && (w.0 >> 16) == 0 => {
            unsafe { let _ = PostMessageW(Some(window), ACTION, WPARAM(w.0 & 0xffff), LPARAM(0)); }
            LRESULT(0)
        }
        WM_CLOSE => {
            unsafe { let _ = PostMessageW(Some(window), ACTION, WPARAM(0), LPARAM(0)); }
            LRESULT(0)
        }
        WM_DESTROY => {
            unsafe { PostQuitMessage(0); }
            LRESULT(0)
        }
        _ => unsafe { DefWindowProcW(window, message, w, l) },
    }
}

fn child(window: HWND, class: PCWSTR, name: PCWSTR, id: usize, position: [i32; 4]) -> Result<HWND> {
    let [x, y, width, height] = position;
    let style = WS_CHILD | if id == 0 { WS_VISIBLE } else { WS_TABSTOP };
    let control = unsafe {
        CreateWindowExW(WINDOW_EX_STYLE(0), class, name, style, x, y, width, height,
                        Some(window), Some(HMENU(id as *mut _)), None, None)
    }.map_err(|e| e.to_string())?;
    unsafe {
        let font = GetStockObject(DEFAULT_GUI_FONT);
        SendMessageW(control, WM_SETFONT, Some(WPARAM(font.0 as usize)), Some(LPARAM(1)));
    }
    Ok(control)
}

struct Com;
impl Drop for Com {
    fn drop(&mut self) { unsafe { CoUninitialize(); } }
}

pub fn start() {
    let folders = match Folders::discover() {
        Ok(folders) => folders,
        Err(error) => {
            show_error(None, &error, Language::default());
            return;
        }
    };
    let language = Language::load(&folders.data);
    if let Err(error) = run(folders, language) {
        show_error(None, &error, language);
    }
}

fn run(folders: Folders, language: Language) -> Result<()> {
    unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok().map_err(|e| e.to_string())?; }
    let _com = Com;
    let executable = std::env::current_exe().map_err(|e| e.to_string())?;
    let root = executable.parent().ok_or_else(|| LaunchError::new("Could not find the launcher folder.", "起動元のフォルダーが見つかりません。"))?;
    let installer = root.join("app").is_dir();
    let layout = if root.join("bin/pcbnew.exe").is_file() {
        Some(Layout::Packaged(root.to_path_buf()))
    } else if !installer {
        load_registration(&folders.data.join(REGISTRATION)).ok()
    } else {
        None
    };
    let class = w!("SmartBoardDimensionLauncher");
    let instance = HINSTANCE(unsafe { GetModuleHandleW(None) }.map_err(|e| e.to_string())?.0);
    let atom = unsafe {
        RegisterClassW(&WNDCLASSW {
            lpfnWndProc: Some(window_proc),
            hInstance: instance,
            hCursor: LoadCursorW(None, IDC_ARROW).map_err(|e| e.to_string())?,
            hbrBackground: HBRUSH((COLOR_WINDOW.0 + 1) as *mut _),
            lpszClassName: class,
            ..Default::default()
        })
    };
    if atom == 0 { return Err(windows::core::Error::from_thread().to_string().into()); }
    let window = unsafe {
        CreateWindowExW(WS_EX_CONTROLPARENT, class, title(language), WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
                        CW_USEDEFAULT, CW_USEDEFAULT, 640, 305, None, None, Some(instance), None)
    }.map_err(|e| e.to_string())?;
    let setup = (|| {
        let hint = child(window, w!("STATIC"), w!(""), 0, [18, 18, 438, 35])?;
        let language_button = child(window, w!("BUTTON"), w!(""), LANGUAGE, [475, 13, 125, 31])?;
        let buttons = [
            child(window, w!("BUTTON"), w!(""), REGISTER, [18, 110, 288, 38])?,
            child(window, w!("BUTTON"), w!(""), INSTALL, [18, 58, 288, 38])?,
            child(window, w!("BUTTON"), w!(""), NEW, [18, 58, 184, 38])?,
            child(window, w!("BUTTON"), w!(""), OPEN, [218, 58, 184, 38])?,
            child(window, w!("BUTTON"), w!(""), EXAMPLE, [418, 58, 184, 38])?,
        ];
        let status = child(window, w!("STATIC"), w!(""), 0, [18, 169, 584, 76])?;
        Ok(App { executable, folders, layout, installer, pending: None, language, language_button, hint, status, buttons })
    })();
    let mut app = match setup {
        Ok(app) => app,
        Err(error) => {
            unsafe { let _ = DestroyWindow(window); }
            return Err(error);
        }
    };
    app.refresh_controls();
    app.apply_language(window);
    unsafe { let _ = ShowWindow(window, SW_SHOW); }
    let mut message = MSG::default();
    loop {
        let received = unsafe { GetMessageW(&mut message, None, 0, 0) };
        if received.0 < 0 {
            unsafe { let _ = DestroyWindow(window); }
            return Err(windows::core::Error::from_thread().to_string().into());
        }
        if received.0 == 0 { return Ok(()); }
        if message.hwnd == window && message.message == ACTION {
            let close = if message.wParam.0 == 0 { app.pending.is_none() } else {
                match app.handle(window, message.wParam.0) {
                    Ok(close) => close,
                    Err(error) => { show_error(Some(window), &error, app.language); false }
                }
            };
            if close {
                unsafe { DestroyWindow(window).map_err(|e| e.to_string())?; }
                return Ok(());
            }
        } else if message.hwnd == window && message.message == WM_TIMER && message.wParam.0 == TIMER {
            app.finish_task(window);
        } else if !unsafe { IsDialogMessageW(window, &message) }.as_bool() {
            unsafe {
                let _ = TranslateMessage(&message);
                DispatchMessageW(&message);
            }
        }
    }
}
