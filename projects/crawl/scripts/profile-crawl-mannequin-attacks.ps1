param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Profiler = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\profile_mannequin_attacks.py"
$Output = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\attack_profiles_measured.json"

foreach ($required in @($Python, $UnrealEditorCmd, $Project, $Profiler)) {
    if (-not (Test-Path $required)) {
        throw "Required attack-profiler input missing: $required"
    }
}

Write-Host "== Attack variety pure tests =="
& $Python -m pytest tests/test_attack_variety.py tests/test_combat_staging.py tests/test_animation_transitions.py -q
if ($LASTEXITCODE -ne 0) {
    throw "Attack variety/profile prerequisite tests failed with exit code $LASTEXITCODE"
}

if (Test-Path $Output) {
    Remove-Item $Output -Force
}

Write-Host ""
Write-Host "== Sequencer-sample Manny attack assets in Unreal =="
$StartedUtc = [DateTime]::UtcNow
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Profiler" -unattended -nop4 -nosplash -log
$ExitCode = $LASTEXITCODE

if (-not (Test-Path $Output)) {
    throw "Attack profiler produced no measurement JSON. Unreal exit code: $ExitCode"
}
if ((Get-Item $Output).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "Attack profiler left stale measurement JSON. Unreal exit code: $ExitCode"
}

$Measured = Get-Content $Output -Raw | ConvertFrom-Json
if ($Measured.protocol -ne "crawl.presentation-attack-profile-measurements.v3") {
    throw "Unexpected attack profiler protocol: $($Measured.protocol)"
}
if ($Measured.evaluation_mode -ne "anim_pose_component_space_root_locked") {
    throw "Attack profiler did not use deterministic component-space AnimPose evaluation."
}
if (@($Measured.profiles).Count -lt 1) {
    throw "Attack profiler measured no animation assets."
}
foreach ($Profile in @($Measured.profiles)) {
    $Variation = $Profile.pose_variation
    if ($null -eq $Variation -or
        ([int]$Variation.unique_forward -le 8 -and [int]$Variation.unique_lateral -le 8 -and [int]$Variation.unique_height -le 8)) {
        throw "Attack profiler returned a frozen pose for $($Profile.asset_name)."
    }
}

Write-Host ""
Write-Host "ATTACK PROFILE MEASUREMENT PASS"
Write-Host "Output: $Output"
Write-Host "Evaluation: $($Measured.evaluation_mode)"
Write-Host "Profiles: $(@($Measured.profiles).Count)"
foreach ($Profile in @($Measured.profiles)) {
    Write-Host ("  {0}: phase={1:N4} forward={2:N2}cm lateral={3:N2}cm height={4:N2}cm duration={5:N3}s variation={6}/{7}/{8}" -f `
        $Profile.asset_name, `
        [double]$Profile.candidate_contact_phase, `
        [double]$Profile.candidate_forward_reach_cm, `
        [double]$Profile.candidate_lateral_reach_cm, `
        [double]$Profile.candidate_contact_height_cm, `
        [double]$Profile.source_duration_seconds, `
        [int]$Profile.pose_variation.unique_forward, `
        [int]$Profile.pose_variation.unique_lateral, `
        [int]$Profile.pose_variation.unique_height)
}
if (@($Measured.missing_assets).Count -gt 0) {
    Write-Warning "Missing attack assets: $($Measured.missing_assets -join ', ')"
}
if ($ExitCode -ne 0) {
    Write-Warning "Unreal returned $ExitCode after writing fresh valid measurements; using artifact validation rather than shutdown status."
}
