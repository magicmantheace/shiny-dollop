param(
    [int]$Crawlers = 50,
    [int]$Floors = 3,
    [int]$MaxSteps = 10000,
    [switch]$SkipFullRegression
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create/activate the repo venv first."
}

Write-Host "== Crawl v0.6 Slices 1-21 focused tests =="
& $Python -m pytest `
    tests/test_crawl_domain.py `
    tests/test_crawl_slices2_6.py `
    tests/test_crawl_slices7_11.py `
    tests/test_crawl_slices12_15.py `
    tests/test_crawl_slices16_18.py `
    tests/test_crawl_slices19_21.py `
    -q
if ($LASTEXITCODE -ne 0) { throw "Focused Crawl tests failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "== Spectator API / Unreal bridge / replay acceptance run =="
& $Python -m livingworld.crawl_spectator_demo `
    --seed "crawl-v06-validation" `
    --crawlers $Crawlers `
    --floors $Floors `
    --max-steps $MaxSteps `
    --output "validation/crawl-v0.6-slices19-21-spectator.json"
if ($LASTEXITCODE -ne 0) { throw "Spectator/replay acceptance run failed with exit code $LASTEXITCODE." }

if (-not $SkipFullRegression) {
    Write-Host ""
    Write-Host "== Full inherited repository regression suite =="
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Full regression suite failed with exit code $LASTEXITCODE." }
}

Write-Host ""
Write-Host "OVERALL PASS - Crawl v0.6 Slices 19-21 validation completed locally."
Write-Host "Report: validation\crawl-v0.6-slices19-21-spectator.json"
