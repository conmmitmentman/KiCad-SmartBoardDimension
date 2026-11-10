# All paths are artificial workspace fixtures. Never starts KiCad or uses the real profile.
param([string]$FixtureParent = (Join-Path $PSScriptRoot 'test-output'))
$ErrorActionPreference = 'Stop'
$fixture = Join-Path ([IO.Path]::GetFullPath($FixtureParent)) ('s-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$native = Split-Path -Parent $PSScriptRoot
. (Join-Path $native 'setup_windows.ps1') -FunctionsOnly
function Assert-True($condition, $message) { if (!$condition) { throw $message } }
$build = Join-Path $fixture 'b 日本語'
foreach ($p in @('pcbnew/pcbnew.exe', 'pcbnew/_pcbnew.dll', 'vcpkg_installed/x64-windows/tools/python3/python.exe')) {
    $file = Join-Path $build $p
    [IO.Directory]::CreateDirectory((Split-Path -Parent $file)) | Out-Null
    [IO.File]::WriteAllText($file, 'fixture')
}
$markers = '数値・計算式 → Enter確定 / Esc取消', '半径 (mm) · 中心固定', '寸法から基板外形を変更'
[IO.File]::WriteAllBytes((Join-Path $build 'pcbnew/pcbnew.dll'), [Text.Encoding]::Unicode.GetBytes(($markers -join "`n")))
$data = Join-Path $fixture 'u 日本語'
$shortcuts = Join-Path $fixture 'shortcuts'
Install-BuildLauncher $build $native $data @($shortcuts) | Out-Null
$settings = Read-LauncherSettings $data
Assert-True ($settings.build_directory -eq $build) 'Build location not persisted'
$stable = Join-Path $data 'build-launcher'
foreach ($name in @('setup_windows.ps1', 'launch_windows.ps1', 'windows/build_identity.ps1', 'examples/circle.kicad_pcb')) {
    Assert-True (Test-Path -LiteralPath (Join-Path $stable $name)) "Missing stable payload: $name"
}
$shortcutArgs = [SmartBoardDimensionSetup.Shortcuts]::Arguments((Join-Path $shortcuts 'スマート基板寸法（ビルド版）.lnk'))
Assert-True ($shortcutArgs.Contains('"' + (Join-Path $stable 'setup_windows.ps1') + '"')) 'Shortcut script path not quoted'
Assert-True ($shortcutArgs.Contains('"' + $data + '"')) 'Shortcut data path not quoted'
Assert-True ($shortcutArgs.Contains('-Launch')) 'Shortcut would rerun first setup'

# Set a genuine-looking user config and repeat setup; preserve it and the sample.
[IO.Directory]::CreateDirectory($settings.config_directory) | Out-Null
[IO.File]::WriteAllText((Join-Path $settings.config_directory 'user-config.txt'), 'keep settings')
$samples = Join-Path $data 'samples'
[IO.Directory]::CreateDirectory($samples) | Out-Null
[IO.File]::WriteAllText((Join-Path $samples 'circle.kicad_pcb'), 'edited sample')
Install-BuildLauncher $build $stable $data @($shortcuts) | Out-Null
Assert-True ((Get-Content -LiteralPath (Join-Path $samples 'circle.kicad_pcb') -Raw) -eq 'edited sample') 'Edited sample overwritten'
Assert-True ((Get-Content -LiteralPath (Join-Path $settings.config_directory 'user-config.txt') -Raw) -eq 'keep settings') 'User settings overwritten'

# Load only the persistent copy as a later process would, without showing a form.
. (Join-Path $stable 'setup_windows.ps1') -FunctionsOnly
$again = Read-LauncherSettings $data
Assert-True ($again.build_directory -eq $build) 'Persistent launcher lost its build location'
$global:SbdSetupCalls = @()
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle)
    $global:SbdSetupCalls += @{FilePath=$FilePath; ArgumentList=$ArgumentList; WorkingDirectory=$WorkingDirectory}
}
$oldPath = $env:PATH
Start-SavedEditor $data
Assert-True ($global:SbdSetupCalls.Count -eq 1) 'Blank board launch was not dispatched'
Assert-True (!$global:SbdSetupCalls[0].ArgumentList) 'Blank board unexpectedly requires a board filename'
Assert-True ($env:PATH -eq $oldPath) 'Launcher changed the caller environment'
$board = Join-Path $fixture 'board with spaces.kicad_pcb'
[IO.File]::WriteAllText($board,'fixture board')
Start-SavedEditor $data $board
Assert-True ($global:SbdSetupCalls[1].ArgumentList -eq ('"' + $board + '"')) 'Board path not quoted'

$settingsBefore = Get-Content -LiteralPath (Join-Path $stable 'settings.json') -Raw
$failed = $false
try { Install-BuildLauncher (Join-Path $fixture 'missing build') $native $data @($shortcuts) } catch { $failed = $true }
Assert-True $failed 'Invalid build accepted'
Assert-True ((Get-Content -LiteralPath (Join-Path $stable 'settings.json') -Raw) -eq $settingsBefore) 'Failed setup replaced working configuration'
[IO.File]::WriteAllText((Join-Path $stable 'settings.json'), '{invalid')
Install-BuildLauncher $build $stable $data @($shortcuts) | Out-Null
Assert-True ((Read-LauncherSettings $data).build_directory -eq $build) 'Reselection did not repair broken launcher settings'
Assert-True (@(Get-ChildItem -LiteralPath $stable -Filter 'settings.json.invalid-*.bak').Count -eq 1) 'Broken settings were not backed up'
Write-Output 'PASS: persisted setup, self-contained launcher, quoted shortcuts, repeat setup, preserved user data, blank/existing board dispatch (mock), invalid setup preserves settings.'
