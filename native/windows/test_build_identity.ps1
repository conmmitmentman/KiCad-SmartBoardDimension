param([Alias('TestRoot')][string]$FixtureParent = (Join-Path $PSScriptRoot 'test-output'))
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'build_identity.ps1')

# All files below are artificial fixtures; no editor or installed build is used.
$fixture = Join-Path $FixtureParent ('identity-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($fixture) | Out-Null
$utf16 = [Text.Encoding]::Unicode
$markers = @('数値・計算式 → Enter確定 / Esc取消', '半径 (mm) · 中心固定', '寸法から基板外形を変更')
function Assert-True($condition, $message) { if (!$condition) { throw $message } }
function Assert-Rejected($path, $message) {
    $rejected = $false
    try { $null = Get-NativeBuild -BuildDirectory $path } catch { $rejected = $true }
    Assert-True $rejected $message
}
function New-FakeBuild($name, $omit) {
    $root = Join-Path $fixture $name
    foreach ($relative in @('pcbnew/pcbnew.exe', 'pcbnew/_pcbnew.dll', 'vcpkg_installed/x64-windows/tools/python3/python.exe')) {
        if ($relative -eq $omit) { continue }
        $path = Join-Path $root $relative
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
        [IO.File]::WriteAllBytes($path, [byte[]](0x4d, 0x5a, 0, 0))
    }
    return $root
}

$official = New-FakeBuild 'official-like'
Assert-Rejected $official 'An unmodified build was accepted based only on file layout'

$native = New-FakeBuild '日本語 と space'
# Put a marker across each 3 MiB read boundary, including a split UTF-16 code unit.
$chunkSize = 3 * 1024 * 1024
$buffer = New-Object byte[] (4 * $chunkSize)
for ($i = 0; $i -lt $markers.Count; $i++) {
    $bytes = $utf16.GetBytes($markers[$i])
    [Array]::Copy($bytes, 0, $buffer, (($i + 1) * $chunkSize - $bytes.Length + 5), $bytes.Length)
}
[IO.File]::WriteAllBytes((Join-Path $native 'pcbnew/_pcbnew.dll'), $buffer)
$resolved = Get-NativeBuild -BuildDirectory (Join-Path $native '.')
Assert-True ($resolved -eq (Get-Item -LiteralPath $native).FullName) 'Native markers crossing chunk boundaries were not detected'

$kiface = New-FakeBuild 'kiface-layout'
[IO.File]::WriteAllBytes((Join-Path $kiface 'pcbnew/pcbnew.kiface'), $buffer)
Assert-True ((Get-NativeBuild -BuildDirectory $kiface) -eq $kiface) 'Native KIFACE binary was not detected'

$anotherDll = New-FakeBuild 'dll-layout'
[IO.File]::WriteAllBytes((Join-Path $anotherDll 'pcbnew/pcbnew.dll'), $buffer)
Assert-True ((Get-NativeBuild -BuildDirectory $anotherDll) -eq $anotherDll) 'Native PCB DLL separate from Python DLL was not detected'

$split = New-FakeBuild 'split-markers'
for ($i = 0; $i -lt $markers.Count; $i++) {
    [IO.File]::WriteAllBytes((Join-Path $split "pcbnew/part$i.dll"), $utf16.GetBytes($markers[$i]))
}
Assert-Rejected $split 'Markers spread among different binaries were accepted'

$sourceOnly = New-FakeBuild 'source-text-only'
[IO.File]::WriteAllBytes((Join-Path $sourceOnly 'pcbnew/_pcbnew.dll'), [Text.Encoding]::UTF8.GetBytes(($markers -join "`n")))
[IO.File]::WriteAllBytes((Join-Path $sourceOnly 'pcbnew/source.h'), $buffer)
Assert-Rejected $sourceOnly 'UTF-8 source text or a source header was accepted as a native binary'

$missing = New-FakeBuild 'missing-python' 'vcpkg_installed/x64-windows/tools/python3/python.exe'
[IO.File]::WriteAllBytes((Join-Path $missing 'pcbnew/_pcbnew.dll'), $buffer)
Assert-Rejected $missing 'Native feature markers bypassed missing runtime validation'

Write-Output 'PASS: unmodified build rejection; native DLL/KIFACE identification; UTF-16 markers across read boundaries; split-marker/source-text rejection; required runtime check; Japanese and spaced paths.'
Write-Output "Artificial fixtures: $fixture"
