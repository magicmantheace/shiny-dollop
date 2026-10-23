param(
    [int]$Years = 1,
    [int]$SnapshotEvery = 10,
    [string]$Seed = "long-horizon-benchmark",
    [string]$WorldName = "Eldara Benchmark",
    [string]$Output = "validation\long-horizon",
    [switch]$NoFailFast
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create .venv and install .[test] first."
}

if ($Years -le 0) {
    throw "Years must be greater than zero."
}
if ($SnapshotEvery -le 0) {
    throw "SnapshotEvery must be greater than zero."
}

# Prevent another project's site-packages from leaking into LivingWorld. This
# specifically protects the benchmark from global/session PYTHONPATH values.
$OriginalPythonPath = $env:PYTHONPATH
try {
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

    $Arguments = @(
        "-m", "livingworld.benchmark",
        "--years", "$Years",
        "--snapshot-every", "$SnapshotEvery",
        "--seed", $Seed,
        "--name", $WorldName,
        "--output", $Output
    )
    if ($NoFailFast) {
        $Arguments += "--no-fail-fast"
    }

    Write-Host "LivingWorld long-horizon benchmark"
    Write-Host "Years: $Years"
    Write-Host "Seed: $Seed"
    Write-Host "Snapshots: every $SnapshotEvery year(s)"
    Write-Host "Output: $Output"
    Write-Host ""

    & $Python @Arguments
    $ExitCode = $LASTEXITCODE
}
finally {
    if ($null -eq $OriginalPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $OriginalPythonPath
    }
}

Write-Host ""
Write-Host "Reports:"
Write-Host "  $Output\BENCHMARK.md"
Write-Host "  $Output\benchmark.json"
Write-Host "  $Output\checkpoint_world.json"
Write-Host "  $Output\maps\"

exit $ExitCode
