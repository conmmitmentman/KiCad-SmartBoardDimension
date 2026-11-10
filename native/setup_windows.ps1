# SPDX-License-Identifier: MIT
[CmdletBinding()]
param(
    [switch]$Launch,
    [switch]$FunctionsOnly,
    [string]$DataDirectory = (Join-Path $env:LOCALAPPDATA 'SmartBoardDimension')
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows\build_identity.ps1')
. (Join-Path $PSScriptRoot 'windows\shortcut.ps1')

function Read-LauncherSettings([string]$DataRoot) {
    $path = Join-Path $DataRoot 'build-launcher\settings.json'
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    $value = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($value.schema -ne 1 -or !($value.build_directory -is [string]) -or !($value.config_directory -is [string])) {
        throw '起動設定を読み込めません。「ビルド先を選び直す」から初回設定をやり直してください。'
    }
    return $value
}

function Write-LauncherShortcut([string]$Folder, [string]$Script, [string]$DataRoot, [string]$Editor) {
    [IO.Directory]::CreateDirectory($Folder) | Out-Null
    Initialize-UnicodeShortcut
    $file = Join-Path $Folder 'スマート基板寸法（ビルド版）.lnk'
    $target = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = '-NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $Script + '" -Launch -DataDirectory "' + $DataRoot + '"'
    [SmartBoardDimensionSetup.Shortcuts]::Save($file, $target, $arguments, (Split-Path -Parent $Script), $Editor)
}

function Install-BuildLauncher([string]$BuildDirectory, [string]$SourceDirectory, [string]$DataRoot, [string[]]$ShortcutFolders) {
    # Feature validation happens before writing settings or shortcuts.
    $build = Get-NativeBuild $BuildDirectory
    $payload = @('setup_windows.ps1', 'launch_windows.ps1', 'windows\build_identity.ps1', 'windows\shortcut.ps1', 'examples\circle.kicad_pcb')
    foreach ($name in $payload) {
        if (!(Test-Path -LiteralPath (Join-Path $SourceDirectory $name) -PathType Leaf)) { throw "初回設定のファイルが不足しています: $name。ZIP全体を展開し直してください。" }
    }
    $stable = Join-Path $DataRoot 'build-launcher'
    [IO.Directory]::CreateDirectory($stable) | Out-Null
    foreach ($name in $payload) {
        $source = [IO.Path]::GetFullPath((Join-Path $SourceDirectory $name))
        $target = [IO.Path]::GetFullPath((Join-Path $stable $name))
        [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
        if ($source -ne $target) { Copy-Item -LiteralPath $source -Destination $target -Force }
    }
    # Keep the same config path on later setup runs. Do not reset KiCad settings.
    try { $previous = Read-LauncherSettings $DataRoot }
    catch {
        $broken = Join-Path $stable 'settings.json'
        Copy-Item -LiteralPath $broken -Destination ($broken + '.invalid-' + [guid]::NewGuid().ToString('N') + '.bak')
        $previous = $null
    }
    $config = if ($previous) { $previous.config_directory } else { Join-Path $DataRoot 'native-1.0' }
    $settings = @{ schema=1; build_directory=$build; config_directory=$config }
    $temp = Join-Path $stable ('settings-' + [guid]::NewGuid().ToString('N') + '.tmp')
    [IO.File]::WriteAllText($temp, ($settings | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temp -Destination (Join-Path $stable 'settings.json') -Force
    foreach ($folder in $ShortcutFolders) {
        Write-LauncherShortcut $folder (Join-Path $stable 'setup_windows.ps1') $DataRoot (Join-Path $build 'pcbnew\pcbnew.exe')
    }
    return $settings
}

function Start-SavedEditor([string]$DataRoot, [string]$Board = '') {
    $settings = Read-LauncherSettings $DataRoot
    if (!$settings) { throw '初回設定がまだです。「ビルド先を選び直す」で設定してください。' }
    # Do not scan the DLL on every launch. Initial setup identified the feature.
    if (!(Test-Path -LiteralPath (Join-Path $settings.build_directory 'pcbnew\pcbnew.exe') -PathType Leaf)) {
        throw '保存したビルド先が見つかりません。移動・削除した場合は「ビルド先を選び直す」で設定し直してください。'
    }
    & (Join-Path $PSScriptRoot 'launch_windows.ps1') -BuildDirectory $settings.build_directory -Board $Board -ConfigDirectory $settings.config_directory
}

if ($FunctionsOnly) { return }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
try {
    if (![Environment]::Is64BitOperatingSystem) { throw '64ビット版Windowsが必要です。' }
    $form = New-Object Windows.Forms.Form
    $form.Text = 'スマート基板寸法 — 初回設定・起動'
    $form.ClientSize = New-Object Drawing.Size(640, 320)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.Font = New-Object Drawing.Font('Yu Gothic UI', 10)
    $label = New-Object Windows.Forms.Label
    $label.SetBounds(20, 15, 600, 75)
    $label.Text = "初回だけ、寸法機能を含むビルドのフォルダーを選びます。`n設定後はデスクトップの「スマート基板寸法（ビルド版）」から起動できます。`n本体のダウンロード・ビルドを自動で行うものではありません。"
    $form.Controls.Add($label)
    $status = New-Object Windows.Forms.Label
    $status.SetBounds(20, 220, 600, 85)
    $status.AutoEllipsis = $true
    $form.Controls.Add($status)
    function Update-Status {
        try {
            $saved = Read-LauncherSettings $DataDirectory
            $status.Text = if ($saved) { "設定済み — 次回から専用アイコンで起動できます。`nビルド先: " + $saved.build_directory } else { '未設定 — 先に「ビルド先を選ぶ」で登録してください。' }
        } catch { $status.Text = $_.Exception.Message }
    }
    function Show-Error($Failure) { [Windows.Forms.MessageBox]::Show($form, $Failure.Exception.Message, 'スマート基板寸法', 'OK', 'Warning') | Out-Null }
    $select = New-Object Windows.Forms.Button
    $select.SetBounds(20, 100, 290, 40)
    $select.Text = 'ビルド先を選ぶ・選び直す（初回設定）'
    $select.Add_Click({
        $dialog = New-Object Windows.Forms.FolderBrowserDialog
        $dialog.Description = 'ビルドフォルダーを選択（例: build\msvc-win64-release）。pcbnew.exe自体を選ぶ必要はありません。'
        $dialog.ShowNewFolderButton = $false
        try {
            if ($dialog.ShowDialog($form) -eq 'OK') {
                $select.Enabled = $false
                $status.Text = '寸法機能を確認して、起動設定を保存しています…'
                $form.Refresh()
                $folders = @([Environment]::GetFolderPath('DesktopDirectory'), (Join-Path ([Environment]::GetFolderPath('Programs')) 'SmartBoardDimension'))
                Install-BuildLauncher $dialog.SelectedPath $PSScriptRoot $DataDirectory $folders | Out-Null
                Update-Status
            }
        } catch { Show-Error $_ } finally { $select.Enabled = $true; $dialog.Dispose() }
    })
    $form.Controls.Add($select)
    $create = New-Object Windows.Forms.Button
    $create.SetBounds(330, 100, 290, 40)
    $create.Text = '新しい基板を開く'
    $create.Add_Click({ try { Start-SavedEditor $DataDirectory } catch { Show-Error $_ } })
    $form.Controls.Add($create)
    $open = New-Object Windows.Forms.Button
    $open.SetBounds(20, 155, 290, 40)
    $open.Text = '保存済みの基板を開く'
    $open.Add_Click({
        $dialog = New-Object Windows.Forms.OpenFileDialog
        $dialog.Filter = 'KiCad基板 (*.kicad_pcb)|*.kicad_pcb'
        try { if ($dialog.ShowDialog($form) -eq 'OK') { Start-SavedEditor $DataDirectory $dialog.FileName } }
        catch { Show-Error $_ } finally { $dialog.Dispose() }
    })
    $form.Controls.Add($open)
    $sample = New-Object Windows.Forms.Button
    $sample.SetBounds(330, 155, 290, 40)
    $sample.Text = '円のサンプルを試す'
    $sample.Add_Click({
        try {
            $dir = Join-Path $DataDirectory 'samples'
            [IO.Directory]::CreateDirectory($dir) | Out-Null
            $file = Join-Path $dir 'circle.kicad_pcb'
            if (!(Test-Path -LiteralPath $file)) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'examples\circle.kicad_pcb') -Destination $file }
            Start-SavedEditor $DataDirectory $file
        } catch { Show-Error $_ }
    })
    $form.Controls.Add($sample)
    Update-Status
    $form.ShowDialog() | Out-Null
    $form.Dispose()
} catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'スマート基板寸法', 'OK', 'Error') | Out-Null; exit 1 }
