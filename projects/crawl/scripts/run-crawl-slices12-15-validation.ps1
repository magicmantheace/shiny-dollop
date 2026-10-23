param(
    [int]$Crawlers = 100,
    [int]$Floors = 3,
    [int]$MaxSteps = 25000,
    [string]$Seed = "crawl-batch3-mvp",
    [switch]$SkipFullRegression
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create/activate the repo venv first."
}

Write-Host "== Crawl v0.4 Slices 1-15 focused tests =="
& $Python -m pytest `
    tests/test_crawl_domain.py `
    tests/test_crawl_slices2_6.py `
    tests/test_crawl_slices7_11.py `
    tests/test_crawl_slices12_15.py `
    -q
if ($LASTEXITCODE -ne 0) { throw "Focused Crawl tests failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "== Headless Crawl MVP gate =="
& $Python -m livingworld.crawl_mvp_demo `
    --seed $Seed `
    --crawlers $Crawlers `
    --floors $Floors `
    --max-steps $MaxSteps `
    --output "validation/crawl-v0.4-slices12-15-mvp.json"
if ($LASTEXITCODE -ne 0) { throw "Headless Crawl MVP gate failed with exit code $LASTEXITCODE." }

if (-not $SkipFullRegression) {
    Write-Host ""
    Write-Host "== Full inherited repository regression suite =="
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Full regression suite failed with exit code $LASTEXITCODE." }
}

Write-Host ""
Write-Host "OVERALL PASS - Crawl Slices 1-15 headless MVP validation completed locally."
Write-Host "Report: validation\crawl-v0.4-slices12-15-mvp.json"
