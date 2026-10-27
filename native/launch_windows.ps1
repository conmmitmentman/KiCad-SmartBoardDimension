# Launch a compiled KiCad 10.0.7 PCB editor using a separate configuration.
param(
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$Board,
    [string]$ConfigDirectory = (Join-Path $env:LOCALAPPDATA 'SmartBoardDimension\native-1.0')
)
$ErrorActionPreference = 'Stop'
$buildDir = (Resolve-Path -LiteralPath $BuildDirectory).Path
$boardPath = (Resolve-Path -LiteralPath $Board).Path
$depsDir = Join-Path $buildDir 'vcpkg_installed\x64-windows'
$editor = Join-Path $buildDir 'pcbnew\pcbnew.exe'
foreach ($required in @($editor, "$buildDir\pcbnew\_pcbnew.dll", "$depsDir\tools\python3\python.exe")) {
    if (!(Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing build output: $required" }
}
if (!(Test-Path -LiteralPath $boardPath -PathType Leaf)) { throw 'Board must be a file.' }
$savedEnvironment = @{}
foreach ($name in @('PATH','PYTHONHOME','PYTHONPATH','KICAD_RUN_FROM_BUILD_DIR','KICAD_USE_EXTERNAL_PYTHONHOME','KICAD_CONFIG_HOME')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:PATH = "$buildDir\common;$buildDir\common\gal;$buildDir\api;$buildDir\3d-viewer\3d_cache\sg;$depsDir\bin;$depsDir\tools\python3;" + $env:PATH
    $env:KICAD_RUN_FROM_BUILD_DIR = '1'
    $env:KICAD_USE_EXTERNAL_PYTHONHOME = '1'
    $env:PYTHONHOME = "$depsDir\tools\python3"
    $env:PYTHONPATH = "$buildDir\pcbnew;$depsDir\tools\python3\Lib\site-packages"
    $env:KICAD_CONFIG_HOME = [IO.Path]::GetFullPath($ConfigDirectory)
    Start-Process -FilePath $editor -ArgumentList ('"' + $boardPath + '"') -WorkingDirectory "$buildDir\pcbnew" -WindowStyle Normal
} finally {
    foreach ($entry in $savedEnvironment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
}
