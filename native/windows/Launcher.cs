// SPDX-License-Identifier: MIT
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Security.Cryptography;
using System.Threading.Tasks;
using System.Windows.Forms;

class Launcher : Form
{
    static string Root = AppDomain.CurrentDomain.BaseDirectory;
    static string UserData = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SmartBoardDimension");
    Label status;
    static string Hash(string file) { using (var s = File.OpenRead(file)) using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(s)).Replace("-", "").ToLowerInvariant(); }
    static string SafePath(string root, string relative)
    {
        string full = Path.GetFullPath(Path.Combine(root, relative));
        if (!full.StartsWith(Path.GetFullPath(root).TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase)) throw new IOException("配布ファイルのパスが不正です。");
        return full;
    }
    static void Verify(string root)
    {
        string[] lines = File.ReadAllLines(Path.Combine(root, "manifest.sha256"));
        if (lines.Length == 0) throw new IOException("配布ファイル一覧が空です。ZIP全体を展開し直してください。");
        foreach (string line in lines)
        {
            if (line.Length < 67 || Hash(SafePath(root, line.Substring(66))) != line.Substring(0, 64))
                throw new IOException("ファイルの検証に失敗しました。ZIP全体を展開し直してください。");
        }
    }
    static void Shortcut(string folder, string target)
    {
        Directory.CreateDirectory(folder);
        dynamic shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell"));
        dynamic link = shell.CreateShortcut(Path.Combine(folder, "スマート基板寸法（ネイティブ版）.lnk"));
        link.TargetPath = target; link.WorkingDirectory = Path.GetDirectoryName(target);
        link.Description = "日本語のPCB寸法編集・通常のKiCadとは別のアプリ";
        link.IconLocation = Path.Combine(Path.GetDirectoryName(target), "bin", "pcbnew.exe");
        link.Save();
    }
    static void PromoteInstall(string stage, string target)
    {
        string backup = null;
        if (Directory.Exists(target))
        {
            backup = target + ".before-repair-" + Guid.NewGuid().ToString("N");
            try { Directory.Move(target, backup); }
            catch (Exception e)
            {
                throw new IOException("修復の準備ができませんでした。スマート基板寸法とPCBエディタを閉じて、もう一度実行してください。元のフォルダーは変更していません。", e);
            }
        }
        try { Directory.Move(stage, target); }
        catch (Exception e)
        {
            if (backup != null)
            {
                try { Directory.Move(backup, target); }
                catch (Exception restoreError)
                {
                    throw new IOException("修復を完了できませんでした。以前のファイルは次の場所に保管されています: " + backup
                        + "\nアプリを閉じて再実行してください。復元エラー: " + restoreError.Message, e);
                }
            }
            throw new IOException("インストールを完了できませんでした。アプリを閉じて再実行してください。以前のファイルは変更していません。", e);
        }
    }
    // Separate file installation from shortcuts/profile changes so repair can be tested in isolation.
    static string InstallInto(string source, string parent)
    {
        Verify(source);
        Directory.CreateDirectory(parent);
        string manifestHash = Hash(Path.Combine(source, "manifest.sha256"));
        string target = Path.Combine(parent, "native-1.0.0-" + manifestHash.Substring(0, 12));
        if (Directory.Exists(target))
        {
            try
            {
                Verify(target);
                if (Hash(Path.Combine(target, "manifest.sha256")) == manifestHash) return target;
            }
            catch (IOException) { /* Build and verify a replacement before touching the old copy. */ }
            catch (UnauthorizedAccessException) { /* A locked copy will produce a clear error below. */ }
        }
        string stage = target + ".staging-" + Guid.NewGuid().ToString("N");
        Directory.CreateDirectory(stage);
        foreach (string file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            string dest = SafePath(stage, file.Substring(source.Length + 1));
            Directory.CreateDirectory(Path.GetDirectoryName(dest)); File.Copy(file, dest);
        }
        Verify(stage);
        PromoteInstall(stage, target);
        return target;
    }
    static string Install()
    {
        string source = Path.Combine(Root, "app");
        string parent = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "SmartBoardDimension");
        string target = InstallInto(source, parent);
        string exe = Path.Combine(target, "SmartBoardDimension.exe");
        Shortcut(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), exe);
        Shortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "SmartBoardDimension"), exe);
        Directory.CreateDirectory(UserData);
        File.WriteAllText(Path.Combine(UserData, "installed-path.txt"), target);
        return exe;
    }
    static void PrepareConfig(string config, string stock)
    {
        Directory.CreateDirectory(config);
        string common = Path.Combine(config, "kicad_common.json");
        if (!File.Exists(common)) File.WriteAllText(common, "{\"system\":{\"language\":\"日本語\"}}", new System.Text.UTF8Encoding(false));
        foreach (string table in new [] { "fp-lib-table", "sym-lib-table", "design-block-lib-table" })
        {
            string target = Path.Combine(config, table);
            if (File.Exists(target)) continue; // Never replace the user's library choices.
            string standard = Path.Combine(stock, "template", table);
            if (File.Exists(standard)) File.Copy(standard, target);
            else File.WriteAllText(target, "(" + table.Replace('-', '_') + " (version 7))\n", new System.Text.UTF8Encoding(false));
        }
    }
    static void StartEditor(string board)
    {
        string stock = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "KiCad", "10.0", "share", "kicad");
        PrepareConfig(Path.Combine(UserData, "config", "10.0"), stock);
        string exe = Path.Combine(Root, "bin", "pcbnew.exe");
        if (!File.Exists(exe) || !File.Exists(Path.Combine(Root,"share","kicad","internat","ja","kicad.mo")))
            throw new IOException("本体または日本語ファイルがありません。インストールをやり直してください。");
        var p = new ProcessStartInfo(exe, String.IsNullOrEmpty(board) ? "" : "\"" + Path.GetFullPath(board) + "\"");
        p.UseShellExecute = false; p.WorkingDirectory = Path.Combine(Root, "bin");
        p.EnvironmentVariables.Remove("KICAD_RUN_FROM_BUILD_DIR");
        p.EnvironmentVariables["KICAD_STOCK_DATA_HOME"] = Path.Combine(Root, "share", "kicad");
        p.EnvironmentVariables["KICAD_CONFIG_HOME"] = Path.Combine(UserData, "config");
        p.EnvironmentVariables["KICAD_USE_EXTERNAL_PYTHONHOME"] = "1";
        p.EnvironmentVariables["PYTHONHOME"] = Path.Combine(Root, "python");
        p.EnvironmentVariables["PYTHONPATH"] = Path.Combine(Root,"bin") + ";" + Path.Combine(Root,"python","Lib","site-packages");
        p.EnvironmentVariables["PATH"] = Path.Combine(Root,"bin") + ";" + Path.Combine(Root,"python") + ";" + Environment.GetFolderPath(Environment.SpecialFolder.System);
        foreach (string item in new [] { "FOOTPRINT:footprints", "SYMBOL:symbols", "3DMODEL:3dmodels", "TEMPLATE:template" })
        {
            string[] parts = item.Split(':'); string path = Path.Combine(stock, parts[1]);
            if (Directory.Exists(path)) p.EnvironmentVariables["KICAD10_" + parts[0] + "_DIR"] = path;
        }
        Process.Start(p);
    }
    void Run(Action action) { try { action(); } catch (Exception e) { MessageBox.Show(this, e.Message, "スマート基板寸法", MessageBoxButtons.OK, MessageBoxIcon.Error); } }
    Launcher()
    {
        Text = "スマート基板寸法 — ネイティブ版 1.0.0"; Font = new Font("Yu Gothic UI", 10);
        ClientSize = new Size(570, 295); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        bool installer = Directory.Exists(Path.Combine(Root, "app"));
        var intro = new Label { Left=24, Top=20, Width=520, Height=68, Text=installer ? "日本語で使えるPCB寸法エディタを導入します。\n管理者権限・コマンド入力は不要です。\n通常のKiCadはそのまま使えます。" : "PCB上の寸法の数字をクリックして、数値・計算式で変更できます。\n長方形の幅・高さ、円の半径・直径に対応しています。\nこの画面から開くとネイティブ版を使えます。" };
        Controls.Add(intro);
        bool installed = Root.StartsWith(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "SmartBoardDimension") + "\\", StringComparison.OrdinalIgnoreCase);
        status = new Label { Left=24, Top=205, Width=520, Height=80, AutoEllipsis=true, Text=installer ? "デスクトップとスタートメニューに専用アイコンを作成します。" : (installed ? "導入済み / 日本語対応" : "展開フォルダーから起動 / 日本語対応") + "\n場所: " + Root };
        Controls.Add(status);
        var primary = new Button { Left=24, Top=100, Width=250, Height=42, Text=installer ? "インストール" : "基板ファイルを開く" };
        Controls.Add(primary);
        primary.Click += async delegate {
            if (installer) {
                primary.Enabled=false; status.Text="ファイルを検証してインストールしています…";
                try { string exe=await Task.Run(()=>Install()); status.Text="インストール完了。専用アイコンから起動できます。"; Process.Start(exe); Close(); }
                catch (Exception e) { status.Text=e.Message; primary.Enabled=true; }
            } else Run(()=> { using(var dialog=new OpenFileDialog { Filter="KiCad基板 (*.kicad_pcb)|*.kicad_pcb", CheckFileExists=true }) if(dialog.ShowDialog(this)==DialogResult.OK) StartEditor(dialog.FileName); });
        };
        if (!installer) {
            var create=new Button { Left=24, Top=150, Width=250, Height=42, Text="新しい基板を作る" }; Controls.Add(create);
            create.Click += delegate { Run(()=>StartEditor(null)); };
            var sample=new Button { Left=290, Top=100, Width=250, Height=42, Text="円のサンプルで試す" }; Controls.Add(sample);
            sample.Click += delegate { Run(()=> { string dir=Path.Combine(UserData,"samples"); Directory.CreateDirectory(dir); string file=Path.Combine(dir,"circle.kicad_pcb"); if(!File.Exists(file))File.Copy(Path.Combine(Root,"examples","circle.kicad_pcb"),file); StartEditor(file); }); };
        }
    }
    [STAThread] static int Main(string[] args)
    {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        try {
            if(!Environment.Is64BitOperatingSystem)throw new Exception("64ビット版Windowsが必要です。");
            if(args.Length==1 && args[0]=="--install-quiet") { Install(); return 0; }
            Application.Run(new Launcher()); return 0;
        } catch(Exception e) { MessageBox.Show(e.Message,"スマート基板寸法"); return 1; }
    }
}
