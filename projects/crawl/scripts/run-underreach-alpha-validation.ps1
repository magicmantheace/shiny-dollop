param(
    [double]$DurationSeconds = 120,
    [int]$ViewerPort = 8011,
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Npm = "C:\Program Files\nodejs\npm.cmd"
$State = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\runtime-qa"

Write-Host "== Underreach Alpha focused runtime tests =="
& $Python -m pytest tests/test_underreach_alpha_runtime.py tests/test_underreach_spectator_viewer.py tests/test_underreach_multichannel_feed.py tests/test_underreach_live_camera.py tests/test_underreach_live_bridge.py -q
if ($LASTEXITCODE -ne 0) { throw "Runtime/regression tests failed." }
Push-Location (Join-Path $RepoRoot "viewer")
try {
    & $Npm test
    if ($LASTEXITCODE -ne 0) { throw "Viewer tests failed." }
    & $Npm run build
    if ($LASTEXITCODE -ne 0) { throw "Viewer build failed." }
} finally { Pop-Location }

if (Test-Path $State) {
    $Resolved = (Resolve-Path -LiteralPath $State).Path
    $Expected = (Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\runtime-qa")
    if ($Resolved -ne $Expected) { throw "Refusing to clear unexpected QA state path." }
    Remove-Item -LiteralPath $Resolved -Recurse -Force
}
& (Join-Path $PSScriptRoot "start-underreach-alpha.ps1") -Profile qa -DurationSeconds $DurationSeconds -ViewerPort $ViewerPort -StateDirectory $State -FaultInjection -UnrealEditorCmd $UnrealEditorCmd
if ($LASTEXITCODE -ne 0) { throw "Fresh Alpha QA runtime failed." }
$ReportPath = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach_alpha_runtime_report.json"
$FreshReportPath = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach_alpha_runtime_report_fresh.json"
$Fresh = Get-Content $ReportPath -Raw | ConvertFrom-Json
if (@($Fresh.faults_exercised).Count -ne 3 -or @($Fresh.faults_exercised | Where-Object { $_ -in @('viewer','feed_api','unreal') }).Count -ne 3) {
    throw "Fresh QA did not complete all three controlled fault/recovery paths."
}
if ($Fresh.canonical_failures -ne 0 -or $Fresh.checkpoint_failures -ne 0 -or -not $Fresh.final_checkpoint_on_shutdown) {
    throw "Fresh QA report failed strict canonical/checkpoint validation."
}
Copy-Item -LiteralPath $ReportPath -Destination $FreshReportPath -Force
& (Join-Path $PSScriptRoot "start-underreach-alpha.ps1") -Profile qa -DurationSeconds 45 -ViewerPort $ViewerPort -StateDirectory $State -Resume -UnrealEditorCmd $UnrealEditorCmd
if ($LASTEXITCODE -ne 0) { throw "Alpha checkpoint resume QA failed." }

$Report = Get-Content $ReportPath -Raw | ConvertFrom-Json
if ($Report.checkpoint_recoveries -lt 1 -or $Report.canonical_failures -ne 0 -or $Report.checkpoint_failures -ne 0 -or -not $Report.final_checkpoint_on_shutdown) {
    throw "Alpha runtime report failed strict canonical/checkpoint validation."
}
$LiveResult = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\live_unreal_result.json"
if (-not (Test-Path $LiveResult)) { throw "Unreal did not emit final live result metadata." }
$BridgeDebug = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\live_bridge_debug.json"
if (-not (Test-Path $BridgeDebug)) { throw "Unreal did not emit live bridge diagnostics." }
$Bridge = Get-Content $BridgeDebug -Raw | ConvertFrom-Json
if ($Bridge.live_skeletal_actor_count -ne 3) {
    throw "Live Unreal validation expected 3 skeletal actors; got $($Bridge.live_skeletal_actor_count)."
}
if (@($Bridge.animation_binding_errors).Count -ne 0) {
    throw "Live Unreal validation reported animation binding errors."
}
foreach ($Contact in @($Bridge.contact_validation)) {
    if ($Contact.planar_error_cm -gt 30.0 -or $Contact.contact_error_cm -gt 45.0) {
        throw "Live contact validation failed for $($Contact.source_event_id): planar=$($Contact.planar_error_cm)cm 3D=$($Contact.contact_error_cm)cm."
    }
    if (-not $Contact.root_locked) {
        throw "Live contact validation did not use the required root-locked attack asset."
    }
}
foreach ($Terminal in @($Bridge.terminal_validation)) {
    if (-not $Terminal.persistent -or $Terminal.maximum_bone_delta_cm -gt 2.0 -or $Terminal.maximum_actor_transform_delta_cm -gt 2.0) {
        throw "Live terminal persistence validation failed for $($Terminal.actor_id)."
    }
}
foreach ($Cut in @($Bridge.camera_cut_records)) {
    if (-not $Cut.validation.geometry_valid -or -not $Cut.validation.los_valid -or -not $Cut.validation.occupancy_valid) {
        throw "Live camera validation failed for $($Cut.shot_id)."
    }
}
Write-Host "UNDERREACH ALPHA SHORT VALIDATION PASS"
