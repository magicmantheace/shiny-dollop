param(
    [int]$Crawlers = 100,
    [int]$Floors = 3,
    [int]$MaxSteps = 5000,
    [string]$Seed = "crawl-evening-demo",
    [switch]$SkipFullRegression
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create/activate the repo venv first."
}

Write-Host "== Crawl v0.4 Slice 1 + Slices 2-6 focused tests =="
& $Python -m pytest tests/test_crawl_domain.py tests/test_crawl_slices2_6.py -q
if ($LASTEXITCODE -ne 0) { throw "Focused Crawl tests failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "== Headless autonomous crawl demo =="
& $Python -m livingworld.crawl_batch_demo `
    --seed $Seed `
    --crawlers $Crawlers `
    --floors $Floors `
    --max-steps $MaxSteps `
    --output "validation/crawl-v0.4-slices2-6-demo.json"
if ($LASTEXITCODE -ne 0) { throw "Headless Crawl demo failed with exit code $LASTEXITCODE." }

if (-not $SkipFullRegression) {
    Write-Host ""
    Write-Host "== Full inherited repository regression suite =="
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Full regression suite failed with exit code $LASTEXITCODE." }
}

Write-Host ""
Write-Host "OVERALL PASS - Crawl Slices 1-6 validation completed locally."
