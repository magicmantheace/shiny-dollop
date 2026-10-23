param(
    [switch]$FocusedOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create/install the repo virtual environment first."
}

$originalPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $RepoRoot "src"

    Write-Host "Running Crawl v0.4 Slice 1 focused validation..."
    & $Python -m pytest tests/test_crawl_domain.py -q
    if ($LASTEXITCODE -ne 0) {
        throw "Crawl Slice 1 focused validation failed with exit code $LASTEXITCODE."
    }

    if (-not $FocusedOnly) {
        Write-Host "Running full inherited regression suite..."
        & $Python -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "Full regression suite failed with exit code $LASTEXITCODE."
        }
    }

    Write-Host "Crawl v0.4 Slice 1 validation PASS."
}
finally {
    if ($null -eq $originalPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $originalPythonPath
    }
}
