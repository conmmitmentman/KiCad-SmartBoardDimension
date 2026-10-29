param([Parameter(Mandatory=$true)][string]$AssemblyPath)
$ErrorActionPreference = 'Stop'
# Run without opening a window or touching the real installation/settings.
$assembly = [Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $AssemblyPath))
$launcher = $assembly.GetType('Launcher', $true)
$flags = [Reflection.BindingFlags]'NonPublic,Static'
$verify = $launcher.GetMethod('Verify', $flags)
$prepare = $launcher.GetMethod('PrepareConfig', $flags)
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
Write-Output 'PASS: valid package, tampering/empty/traversal/malformed rejection, Japanese defaults, preserved settings, stock library discovery.'
Write-Output "Test fixtures: $testRoot"
