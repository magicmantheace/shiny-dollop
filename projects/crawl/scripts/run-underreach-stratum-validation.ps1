param(
    [string]$Seed = "underreach-29b1-proof",
    [int]$Stratum = 0,
    [int]$Sectors = 12
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$OutDir = Join-Path $RepoRoot "validation\underreach-29b1"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Manifest = Join-Path $OutDir "stratum-environment.json"
$RepeatManifest = Join-Path $OutDir "stratum-environment-repeat.json"

Write-Host "[29B.1] Focused deterministic Stratum tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29B.1] Generate proof manifest"
$env:PYTHONPATH = Join-Path $RepoRoot "src"
& $Python scripts/generate-underreach-stratum-environment.py --seed $Seed --stratum $Stratum --sectors $Sectors --output $Manifest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29B.1] Reproduce proof manifest from identical inputs"
& $Python scripts/generate-underreach-stratum-environment.py --seed $Seed --stratum $Stratum --sectors $Sectors --output $RepeatManifest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$FirstHash = (Get-FileHash -Algorithm SHA256 $Manifest).Hash
$RepeatHash = (Get-FileHash -Algorithm SHA256 $RepeatManifest).Hash
$FirstDigest = (Get-Content -Raw $Manifest | ConvertFrom-Json).digest
$RepeatDigest = (Get-Content -Raw $RepeatManifest | ConvertFrom-Json).digest
if ($FirstHash -ne $RepeatHash -or $FirstDigest -ne $RepeatDigest) {
    Write-Error "[29B.1] FAIL: repeated generation was not identical"
    exit 1
}
Write-Host "[29B.1] Reproducibility PASS"
Write-Host "digest=$FirstDigest"
Remove-Item -Force $RepeatManifest

Write-Host "[29B.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29B.1] PASS"
Write-Host "Manifest: $Manifest"
