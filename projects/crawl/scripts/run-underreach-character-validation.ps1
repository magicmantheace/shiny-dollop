param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [int]$SimulationSteps = 90,
    [switch]$SkipBlender,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generated29A1 = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\29a1"

foreach ($Required in @($Python, $Project, $UnrealEditorCmd)) {
    if (-not (Test-Path $Required)) { throw "Required 29A.1 input is missing: $Required" }
}

Write-Host "== Character DNA / Factory tests =="
& $Python -m pytest tests/test_character_dna.py tests/test_underreach_live_bridge.py -q
if ($LASTEXITCODE -ne 0) { throw "29A.1 focused tests failed." }

if (-not $SkipBlender) {
    Write-Host "== Deterministic MPFB/Blender build =="
    & (Join-Path $PSScriptRoot "build-underreach-mpfb-descenders.ps1")
}

Write-Host "== Unreal skeletal import =="
$ImportReport = Join-Path $Generated29A1 "unreal_character_import_report.json"
$Started = [DateTime]::UtcNow
& $UnrealEditorCmd $Project -run=pythonscript "-script=$RepoRoot\unreal\CrawlPresentation\Content\Python\import_underreach_characters.py" -unattended -nop4 -nosplash -NullRHI -log
if (-not (Test-Path $ImportReport) -or (Get-Item $ImportReport).LastWriteTimeUtc -lt $Started.AddSeconds(-1)) {
    throw "Unreal character import left stale metadata (exit $LASTEXITCODE)."
}

Write-Host "== Imported animation pose validation =="
$PoseReport = Join-Path $Generated29A1 "animation_pose_validation.json"
$Started = [DateTime]::UtcNow
& $UnrealEditorCmd $Project -run=pythonscript "-script=$RepoRoot\unreal\CrawlPresentation\Content\Python\validate_underreach_character_animation.py" -unattended -nop4 -nosplash -NullRHI -log
if (-not (Test-Path $PoseReport) -or (Get-Item $PoseReport).LastWriteTimeUtc -lt $Started.AddSeconds(-1)) {
    throw "Unreal pose validation left stale metadata (exit $LASTEXITCODE)."
}

$ViewerArgs = @{
    SimulationSteps = $SimulationSteps
    UnrealEditorCmd = $UnrealEditorCmd
}
if ($SkipRender) { $ViewerArgs["SkipRender"] = $true }
& (Join-Path $PSScriptRoot "run-underreach-spectator-viewer-validation.ps1") @ViewerArgs

Write-Host "== Fresh-process saved sequence validation =="
& $UnrealEditorCmd $Project "-ExecutePythonScript=$RepoRoot\unreal\CrawlPresentation\Content\Python\validate_underreach_29a1_render_sequence.py" -unattended -nop4 -nosplash -log
if ($LASTEXITCODE -ne 0) { throw "Saved render-sequence pose validation failed." }
& $UnrealEditorCmd $Project "-ExecutePythonScript=$RepoRoot\unreal\CrawlPresentation\Content\Python\validate_underreach_29a1_level.py" -unattended -nop4 -nosplash -log
if ($LASTEXITCODE -ne 0) { throw "Saved character level validation failed." }

Write-Host "UNDERREACH 29A.1 CHARACTER VALIDATION PASS"
Write-Host "Reports: $Generated29A1"
