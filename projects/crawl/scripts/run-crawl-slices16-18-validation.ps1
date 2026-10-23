param(
    [int]$Seeds = 20,
    [int]$Crawlers = 100,
    [int]$Floors = 3,
    [int]$MaxSteps = 25000,
    [switch]$SkipReplay,
    [switch]$SkipFullRegression
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create/activate the repo venv first."
}

Write-Host "== Crawl v0.5 Slices 1-18 focused tests =="
& $Python -m pytest `
    tests/test_crawl_domain.py `
    tests/test_crawl_slices2_6.py `
    tests/test_crawl_slices7_11.py `
    tests/test_crawl_slices12_15.py `
    tests/test_crawl_slices16_18.py `
    -q
if ($LASTEXITCODE -ne 0) { throw "Focused Crawl tests failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "== Crawl Observatory diagnostic snapshot =="
& $Python -m livingworld.crawl_observatory_demo `
    --seed "crawl-v05-observatory" `
    --crawlers ([Math]::Min($Crawlers, 100)) `
    --floors ([Math]::Min($Floors, 3)) `
    --max-steps $MaxSteps `
    --output "validation/crawl-v0.5-observatory.json"
if ($LASTEXITCODE -ne 0) { throw "Crawl Observatory demo failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "== Multi-seed deterministic validation matrix =="
$MatrixArgs = @(
    "-m", "livingworld.crawl_scale_validation",
    "--base-seed", "crawl-v05-validation",
    "--seeds", $Seeds,
    "--crawlers", $Crawlers,
    "--floors", $Floors,
    "--max-steps", $MaxSteps,
    "--output", "validation/crawl-v0.5-slices16-18-matrix.json"
)
if ($SkipReplay) { $MatrixArgs += "--skip-replay" }
& $Python @MatrixArgs
if ($LASTEXITCODE -ne 0) { throw "Multi-seed Crawl validation failed with exit code $LASTEXITCODE." }

if (-not $SkipFullRegression) {
    Write-Host ""
    Write-Host "== Full inherited repository regression suite =="
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Full regression suite failed with exit code $LASTEXITCODE." }
}

Write-Host ""
Write-Host "OVERALL PASS - Crawl v0.5 Slices 16-18 validation completed locally."
Write-Host "Matrix: validation\crawl-v0.5-slices16-18-matrix.json"
Write-Host "Observatory: validation\crawl-v0.5-observatory.json"
