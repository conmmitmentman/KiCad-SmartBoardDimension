#Requires -Version 5.1
<#
  KiCad 10 スマート基板寸法：オフライン導入・更新・復元ツール
  対象の __init__.py / geometry.py / updater.py をコピー。外部通信や管理者権限は不要。
#>
[CmdletBinding()]
param(
    [ValidateSet('Install', 'Update', 'Rollback')]
    [string]$Mode = 'Install',
    [string]$Destination = ''
)

$ErrorActionPreference = 'Stop'
$pluginName = 'smart_board_dimension'
$sourceRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $sourceRoot $pluginName
$files = @('__init__.py', 'geometry.py', 'updater.py')
$required = @('__init__.py', 'geometry.py')
$backupRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'SmartBoardDimension\backups'

function Exists-Plugin([string]$candidate) {
    return (Test-Path -LiteralPath (Join-Path $candidate '__init__.py') -PathType Leaf)
}

function Get-InstallTarget() {
    if ($Destination) {
        $full = [System.IO.Path]::GetFullPath($Destination)
        if ((Split-Path $full -Leaf) -ne $pluginName) {
            throw "-Destination には '$pluginName' フォルダを指定してください: $full"
        }
        return $full
    }

    $docs = [Environment]::GetFolderPath('MyDocuments')
    $candidates = New-Object 'System.Collections.Generic.List[string]'
    if ($docs) { $candidates.Add((Join-Path $docs 'KiCad\10.0\scripting\plugins\smart_board_dimension')) }
    if ($env:USERPROFILE) {
        $candidates.Add((Join-Path $env:USERPROFILE 'Documents\KiCad\10.0\scripting\plugins\smart_board_dimension'))
    }
    if ($env:APPDATA) {
        $candidates.Add((Join-Path $env:APPDATA 'kicad\10.0\scripting\plugins\smart_board_dimension'))
    }
    $candidates = @($candidates | Select-Object -Unique)
    $existing = @($candidates | Where-Object { Exists-Plugin $_ })
    if ($existing.Count -gt 1) {
        throw "複数のインストール先が見つかりました。-Destination を指定してください:`n$($existing -join "`n")"
    }
    if ($existing.Count -eq 1) { return $existing[0] }
    if ($Mode -ne 'Install') {
        throw '既存のプラグインが見つかりません。先にインストールするか、-Destination で配置先を指定してください。'
    }
    if (-not $docs) { throw 'Windowsの「ドキュメント」フォルダが見つかりません。' }
    return (Join-Path $docs 'KiCad\10.0\scripting\plugins\smart_board_dimension')
}

function Read-Version([string]$folder) {
    $file = Join-Path $folder '__init__.py'
    if (-not (Test-Path -LiteralPath $file)) { return '不明' }
    $found = Select-String -LiteralPath $file -Pattern '^PLUGIN_VERSION\s*=\s*[''"]([^''"]+)[''"]' | Select-Object -First 1
    if ($found) { return $found.Matches[0].Groups[1].Value }
    return '不明'
}

function Create-Backup([string]$target) {
    foreach ($filename in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $target $filename) -PathType Leaf)) {
            throw "既存プラグインのファイルが不足しています（中断）: $filename"
        }
    }
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $key = '{0:yyyyMMdd-HHmmss}-{1}' -f (Get-Date), ([guid]::NewGuid().ToString('N').Substring(0,8))
    $folder = Join-Path $backupRoot $key
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    $savedFiles = @()
    foreach ($filename in $files) {
        $path = Join-Path $target $filename
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Copy-Item -LiteralPath $path -Destination (Join-Path $folder $filename) -ErrorAction Stop
            $savedFiles += $filename
        }
    }
    $info = @{
        target = [System.IO.Path]::GetFullPath($target)
        previous_version = Read-Version $target
        old_files = $savedFiles
        new_files = $files
        saved_at = (Get-Date).ToString('o')
    }
    $info | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $folder 'metadata.json') -Encoding UTF8
    return $folder
}

function Restore-Files([string]$folder, [string]$target) {
    foreach ($filename in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $folder $filename) -PathType Leaf)) {
            throw "バックアップが不完全なため復元できません: $folder"
        }
    }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    foreach ($filename in $files) {
        $saved = Join-Path $folder $filename
        $dest = Join-Path $target $filename
        if (Test-Path -LiteralPath $saved -PathType Leaf) {
            Copy-Item -LiteralPath $saved -Destination $dest -Force
        }
        elseif (Test-Path -LiteralPath $dest -PathType Leaf) {
            # 旧版に存在しなかったファイルは復元時に削除する。
            Remove-Item -LiteralPath $dest -Force
        }
    }
}

try {
    Write-Host "スマート基板寸法 / KiCad 10 / $Mode"
    if (Get-Process -Name 'pcbnew' -ErrorAction SilentlyContinue) {
        throw 'KiCadのPCBエディタを終了してから実行してください。'
    }
    $target = Get-InstallTarget
    Write-Host "対象: $target"

    if ($Mode -eq 'Rollback') {
        if (-not (Test-Path -LiteralPath $backupRoot -PathType Container)) {
            throw '復元できるバックアップがありません。'
        }
        $chosen = $null
        foreach ($folder in (Get-ChildItem -LiteralPath $backupRoot -Directory | Sort-Object Name -Descending)) {
            $metaFile = Join-Path $folder.FullName 'metadata.json'
            if (-not (Test-Path -LiteralPath $metaFile -PathType Leaf)) { continue }
            $meta = Get-Content -LiteralPath $metaFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ([string]::Equals($meta.target, [System.IO.Path]::GetFullPath($target),
                    [System.StringComparison]::OrdinalIgnoreCase)) {
                $chosen = $folder.FullName
                break
            }
        }
        if (-not $chosen) { throw 'このインストール先に一致する復元用バックアップはありません。' }
        Restore-Files $chosen $target
        Rename-Item -LiteralPath (Join-Path $chosen 'metadata.json') -NewName 'metadata.restored.json'
        Write-Host "復元完了: $(Read-Version $target)" -ForegroundColor Green
        Write-Host 'PCBエディタを起動し、動作を確認してください。'
        exit 0
    }

    foreach ($filename in $files) {
        $item = Join-Path $source $filename
        if (-not (Test-Path -LiteralPath $item -PathType Leaf)) {
            throw "プラグインのファイルがありません: $item`nZIP全体を展開してから実行してください。"
        }
    }

    $installed = Exists-Plugin $target
    if ($Mode -eq 'Update' -and -not $installed) {
        throw 'インストール済みのプラグインがありません。Windows_インストール.bat を使ってください。'
    }
    $previousBackup = $null
    if ($installed) {
        $previousBackup = Create-Backup $target
        Write-Host "更新前のバックアップ: $previousBackup"
    }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    try {
        foreach ($filename in $files) {
            Copy-Item -LiteralPath (Join-Path $source $filename) -Destination (Join-Path $target $filename) -Force
        }
    }
    catch {
        if ($previousBackup) {
            Restore-Files $previousBackup $target
        }
        else {
            foreach ($filename in $files) {
                Remove-Item -LiteralPath (Join-Path $target $filename) -ErrorAction SilentlyContinue
            }
        }
        throw
    }
    Write-Host "導入完了: v$(Read-Version $target)" -ForegroundColor Green
    Write-Host 'Windows再起動時の再インストールは不要です。'
    Write-Host 'KiCadのPCBエディタを起動して「ツール > 外部プラグイン」から実行できます。'
    exit 0
}
catch {
    Write-Host "失敗: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
