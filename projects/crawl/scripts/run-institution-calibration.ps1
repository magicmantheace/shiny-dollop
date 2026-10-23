param(
    [int]$Years = 100,
    [string]$Seed = "institutions-calibration-v0.3",
    [string]$WorldName = "Eldara Institutional Calibration",
    [string]$OutputDirectory = "validation\institution-calibration",
    [switch]$NoFailFast
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python."
}

$originalPythonPath = $env:PYTHONPATH
try {
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

    $arguments = @(
        "-m", "livingworld.institution_benchmark",
        "--years", $Years,
        "--seed", $Seed,
        "--name", $WorldName,
        "--output", $OutputDirectory
    )
    if ($NoFailFast) {
        $arguments += "--no-fail-fast"
    }

    & $Python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Institutional calibration failed with exit code $LASTEXITCODE."
    }
}
finally {
    if ($null -eq $originalPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $originalPythonPath
    }
}
