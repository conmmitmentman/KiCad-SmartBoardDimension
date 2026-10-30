param([Parameter(Mandatory=$true)][string]$AssemblyPath)
$ErrorActionPreference = 'Stop'
# Run without opening a window or touching the real installation/settings.
$assembly = [Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $AssemblyPath))
$launcher = $assembly.GetType('Launcher', $true)
$flags = [Reflection.BindingFlags]'NonPublic,Static'
$verify = $launcher.GetMethod('Verify', $flags)
$prepare = $launcher.GetMethod('PrepareConfig', $flags)
$installInto = $launcher.GetMethod('InstallInto', $flags)
$promote = $launcher.GetMethod('PromoteInstall', $flags)
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('sbd-launcher-test-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($testRoot) | Out-Null
$utf8 = New-Object Text.UTF8Encoding($false)
function Write-TestFile($path, $value) { [IO.File]::WriteAllText($path, $value, $utf8) }
function Assert-True($condition, $message) { if (!$condition) { throw $message } }
function Assert-Rejected($action, $message) {
    $rejected = $false
    try { & $action } catch { $rejected = $true }
    Assert-True $rejected $message
}

$payload = Join-Path $testRoot 'payload.txt'
$manifest = Join-Path $testRoot 'manifest.sha256'
Write-TestFile $payload 'verified payload'
$digest = (Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash.ToLowerInvariant()
Write-TestFile $manifest ($digest + '  payload.txt')
$verify.Invoke($null, [object[]][string[]]@($testRoot))
Write-TestFile $payload 'tampered payload'
Assert-Rejected { $verify.Invoke($null, [object[]][string[]]@($testRoot)) } 'Tampered payload was accepted'
Write-TestFile $manifest ''
Assert-Rejected { $verify.Invoke($null, [object[]][string[]]@($testRoot)) } 'Empty manifest was accepted'
Write-TestFile $manifest ($digest + '  ../outside.txt')
Assert-Rejected { $verify.Invoke($null, [object[]][string[]]@($testRoot)) } 'Path outside package was accepted'
Write-TestFile $manifest 'invalid'
Assert-Rejected { $verify.Invoke($null, [object[]][string[]]@($testRoot)) } 'Malformed manifest was accepted'

$config = Join-Path $testRoot 'config'
$stock = Join-Path $testRoot 'stock'
$prepare.Invoke($null, [object[]][string[]]@($config, $stock))
$common = Join-Path $config 'kicad_common.json'
Assert-True ((Get-Content -LiteralPath $common -Raw -Encoding UTF8 | ConvertFrom-Json).system.language -eq '日本語') 'First-run language is not Japanese'
Assert-True ((Get-Content -LiteralPath (Join-Path $config 'fp-lib-table') -Raw) -match 'fp_lib_table') 'Empty footprint table missing'

Write-TestFile $common '{"system":{"language":"English"}}'
Write-TestFile (Join-Path $config 'fp-lib-table') '(fp_lib_table (version 7) (lib (name "User")))'
$prepare.Invoke($null, [object[]][string[]]@($config, $stock))
Assert-True ((Get-Content -LiteralPath $common -Raw) -match 'English') 'Existing language overwritten'
Assert-True ((Get-Content -LiteralPath (Join-Path $config 'fp-lib-table') -Raw) -match 'User') 'Existing library choices overwritten'

[IO.Directory]::CreateDirectory((Join-Path $stock 'template')) | Out-Null
Write-TestFile (Join-Path $stock 'template/fp-lib-table') '(fp_lib_table (version 7) (lib (name "Stock")))'
$fresh = Join-Path $testRoot 'fresh'
$prepare.Invoke($null, [object[]][string[]]@($fresh, $stock))
Assert-True ((Get-Content -LiteralPath (Join-Path $fresh 'fp-lib-table') -Raw) -match 'Stock') 'Stock libraries not detected'

$package = Join-Path $testRoot 'package'
$installParent = Join-Path $testRoot 'installations'
[IO.Directory]::CreateDirectory($package) | Out-Null
$sourcePayload = Join-Path $package 'payload.txt'
Write-TestFile $sourcePayload 'clean package'
$sourceDigest = (Get-FileHash -LiteralPath $sourcePayload -Algorithm SHA256).Hash.ToLowerInvariant()
Write-TestFile (Join-Path $package 'manifest.sha256') ($sourceDigest + '  payload.txt')
$installed = $installInto.Invoke($null, [object[]][string[]]@($package, $installParent))
Assert-True ((Get-Content -LiteralPath (Join-Path $installed 'payload.txt') -Raw) -eq 'clean package') 'Initial install failed'
$same = $installInto.Invoke($null, [object[]][string[]]@($package, $installParent))
Assert-True ($same -eq $installed) 'Healthy reinstall changed destination'
Assert-True (@(Get-ChildItem -LiteralPath $installParent -Directory).Count -eq 1) 'Healthy reinstall created another copy'

Write-TestFile (Join-Path $installed 'payload.txt') 'damaged installed file'
Write-TestFile (Join-Path $installed 'user-note.txt') 'preserve this file'
$repaired = $installInto.Invoke($null, [object[]][string[]]@($package, $installParent))
Assert-True ($repaired -eq $installed) 'Repair changed the shortcut destination'
Assert-True ((Get-Content -LiteralPath (Join-Path $repaired 'payload.txt') -Raw) -eq 'clean package') 'Repair did not restore package contents'
$backups = @(Get-ChildItem -LiteralPath $installParent -Directory | Where-Object Name -Match '\.before-repair-')
Assert-True ($backups.Count -eq 1) 'Repair did not preserve the previous directory'
Assert-True ((Get-Content -LiteralPath (Join-Path $backups[0].FullName 'user-note.txt') -Raw) -eq 'preserve this file') 'Repair lost a user-created file'
Assert-True ((Get-Content -LiteralPath (Join-Path $backups[0].FullName 'payload.txt') -Raw) -eq 'damaged installed file') 'Repair overwrote the old copy'

Write-TestFile $sourcePayload 'damaged download'
Assert-Rejected { $installInto.Invoke($null, [object[]][string[]]@($package, $installParent)) } 'Damaged source package accepted during reinstall'
Assert-True ((Get-Content -LiteralPath (Join-Path $installed 'payload.txt') -Raw) -eq 'clean package') 'Failed install changed working files'

# Exercise rollback after the existing directory has been moved aside, without deleting anything.
$rollbackTarget = Join-Path $testRoot 'rollback-target'
[IO.Directory]::CreateDirectory($rollbackTarget) | Out-Null
Write-TestFile (Join-Path $rollbackTarget 'marker.txt') 'original copy'
$missingStage = Join-Path $testRoot 'missing-stage'
Assert-Rejected { $promote.Invoke($null, [object[]][string[]]@($missingStage, $rollbackTarget)) } 'Promotion from a missing stage unexpectedly succeeded'
Assert-True ((Get-Content -LiteralPath (Join-Path $rollbackTarget 'marker.txt') -Raw) -eq 'original copy') 'Failed promotion did not restore the previous directory'
Assert-True (@(Get-ChildItem -LiteralPath $testRoot -Directory | Where-Object Name -Match '^rollback-target\.before-repair-').Count -eq 0) 'Rollback left the original directory at the backup path'

Write-Output 'PASS: package verification, Japanese defaults, preserved settings, stock library discovery, repeat install, repair with backup, failed-source preservation, promotion rollback.'
Write-Output "Test fixtures: $testRoot"
