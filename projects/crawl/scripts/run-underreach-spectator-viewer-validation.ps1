param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [int]$SimulationSteps = 90,
    [int]$ViewerPort = 8011,
    [switch]$ManualControl,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$AcceptedBase = "cd7074bbbfd854481e47c037555965aff8567688"
git merge-base --is-ancestor $AcceptedBase HEAD
if ($LASTEXITCODE -ne 0) { throw "Current branch does not descend from the accepted 28B.3 baseline." }

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Npm = "C:\Program Files\nodejs\npm.cmd"
$Viewer = Join-Path $RepoRoot "viewer"
$ViewerDist = Join-Path $Viewer "dist"
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generated = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated"
$Spool = Join-Path $Generated "LiveBridge"
$ConsumerScript = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\consume_underreach_live_bridge.py"
$LiveResult = Join-Path $Generated "live_unreal_result.json"
$BridgeDebug = Join-Path $Generated "live_bridge_debug.json"
$SchedulerDebug = Join-Path $Generated "live_scheduler_debug.json"
$ProducerDebug = Join-Path $Generated "live_producer_debug.json"
$CameraDebug = Join-Path $Generated "live_camera_debug.json"
$ChannelDebug = Join-Path $Generated "feed_channels_debug.json"
$FocusLedger = Join-Path $Generated "feed_focus_ledger.json"
$ViewerState = Join-Path $Generated "viewer_state_snapshot.json"
$ViewerDebug = Join-Path $Generated "viewer_debug.json"
$Logs = Join-Path $Generated "Logs"
$UnrealLog = Join-Path $Logs "underreach-spectator-viewer.log"
$UnrealStdout = Join-Path $Logs "underreach-spectator-viewer-stdout.log"
$UnrealStderr = Join-Path $Logs "underreach-spectator-viewer-stderr.log"
$ProducerStdout = Join-Path $Logs "underreach-spectator-producer-stdout.log"
$ProducerStderr = Join-Path $Logs "underreach-spectator-producer-stderr.log"
$BaseUrl = "http://127.0.0.1:$ViewerPort"

foreach ($Required in @($UnrealEditorCmd, $Project, $Python, $Npm)) {
    if (-not (Test-Path $Required)) { throw "Required local validation input is missing: $Required" }
}

Write-Host "== Underreach 28C.1 backend and regression tests =="
& $Python -m pytest tests/test_underreach_spectator_viewer.py tests/test_underreach_multichannel_feed.py tests/test_underreach_live_camera.py tests/test_underreach_live_bridge.py -q
if ($LASTEXITCODE -ne 0) { throw "Spectator viewer backend/regression tests failed." }

Write-Host "== Underreach 28C.1 frontend tests/build =="
Push-Location $Viewer
try {
    & $Npm test
    if ($LASTEXITCODE -ne 0) { throw "Spectator viewer frontend tests failed." }
    & $Npm run build
    if ($LASTEXITCODE -ne 0) { throw "Spectator viewer frontend build failed." }
} finally { Pop-Location }

New-Item -ItemType Directory -Path $Logs -Force | Out-Null
if (Test-Path $Spool) { Remove-Item -LiteralPath $Spool -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $Spool "deliveries") -Force | Out-Null
foreach ($Path in @($LiveResult, $BridgeDebug, $SchedulerDebug, $ProducerDebug, $CameraDebug, $ChannelDebug, $FocusLedger, $ViewerState, $ViewerDebug, $UnrealLog, $UnrealStdout, $UnrealStderr, $ProducerStdout, $ProducerStderr)) {
    if (Test-Path $Path) { Remove-Item -LiteralPath $Path -Force }
}

Write-Host "== Start local-only spectator viewer and deterministic Descent =="
$ProducerArgs = @(
    "-m", "livingworld.underreach_multichannel_demo",
    "--spool", $Spool,
    "--steps", "$SimulationSteps",
    "--poll-seconds", "0.55",
    "--external-controls",
    "--viewer-host", "127.0.0.1",
    "--viewer-port", "$ViewerPort",
    "--viewer-static-directory", $ViewerDist,
    "--viewer-hold-seconds", "30"
)
$ProducerProcess = Start-Process -FilePath $Python -ArgumentList $ProducerArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $ProducerStdout -RedirectStandardError $ProducerStderr -PassThru

$Bootstrap = Join-Path $Spool "bootstrap.json"
$Deadline = [DateTime]::UtcNow.AddSeconds(60)
while ((-not (Test-Path $Bootstrap) -or -not (Test-Path $ViewerDist)) -and [DateTime]::UtcNow -lt $Deadline) { Start-Sleep -Milliseconds 100 }
if (-not (Test-Path $Bootstrap)) { throw "Spectator producer did not emit bootstrap." }

Write-Host "== Launch one persistent Unreal consumer =="
$ValidationStarted = [DateTime]::UtcNow
$UnrealArgs = @($Project, "-ExecutePythonScript=$ConsumerScript", "-unattended", "-nop4", "-nosplash", "-abslog=$UnrealLog")
$UnrealProcess = Start-Process -FilePath $UnrealEditorCmd -ArgumentList $UnrealArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $UnrealStdout -RedirectStandardError $UnrealStderr -PassThru

$Deadline = [DateTime]::UtcNow.AddSeconds(90)
$State = $null
while ($null -eq $State -and [DateTime]::UtcNow -lt $Deadline) {
    try { $State = Invoke-RestMethod -Uri "$BaseUrl/api/feed/viewer/state?viewer_id=viewer_local_alpha" -TimeoutSec 2 } catch { Start-Sleep -Milliseconds 250 }
}
if ($null -eq $State) { throw "Spectator viewer did not become reachable at $BaseUrl." }
Write-Host "Viewer URL: $BaseUrl"

if (-not $ManualControl) {
    $Available = @($State.descenders | Where-Object { $_.camera_available -and -not $_.terminal } | Select-Object -First 2)
    if ($Available.Count -lt 2) { throw "Viewer did not expose two camera-available Descenders." }
    function Invoke-ViewerControl([string]$Path, [hashtable]$Body) {
        Invoke-RestMethod -Uri "$BaseUrl$Path" -Method Post -ContentType "application/json" -Body ($Body | ConvertTo-Json -Compress) -TimeoutSec 5
    }
    $Tick = [int]$State.focus.presentation_tick
    $FirstBody = @{ viewer_id = "viewer_local_alpha"; request_id = "viewer_follow_a"; requested_at_presentation_tick = $Tick; descender_id = $Available[1].descender_id }
    [void](Invoke-ViewerControl "/api/feed/live/follow" $FirstBody)
    Start-Sleep -Seconds 2
    $State = Invoke-RestMethod -Uri "$BaseUrl/api/feed/viewer/state?viewer_id=viewer_local_alpha"
    if ($State.focus.mode -ne "manual" -or $State.focus.active_descender_id -ne $Available[1].descender_id) { throw "First viewer follow was not confirmed." }
    $SecondBody = @{ viewer_id = "viewer_local_alpha"; request_id = "viewer_follow_b"; requested_at_presentation_tick = [int]$State.focus.presentation_tick; descender_id = $Available[0].descender_id }
    [void](Invoke-ViewerControl "/api/feed/live/follow" $SecondBody)
    [void](Invoke-ViewerControl "/api/feed/live/follow" $SecondBody)
    $InvalidBody = @{ viewer_id = "viewer_local_alpha"; request_id = "viewer_invalid"; requested_at_presentation_tick = [int]$State.focus.presentation_tick; descender_id = "unknown_descender" }
    try { [void](Invoke-ViewerControl "/api/feed/live/follow" $InvalidBody); throw "Invalid follow unexpectedly succeeded." } catch { if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw } }
    Start-Sleep -Seconds 2
    $State = Invoke-RestMethod -Uri "$BaseUrl/api/feed/viewer/state?viewer_id=viewer_local_alpha"
    $ReleaseBody = @{ viewer_id = "viewer_local_alpha"; request_id = "viewer_release_auto"; requested_at_presentation_tick = [int]$State.focus.presentation_tick }
    [void](Invoke-ViewerControl "/api/feed/live/release" $ReleaseBody)
    Write-Host "Automated viewer follow/switch/duplicate/invalid/release sequence acknowledged."
} else {
    Write-Host "Manual control mode: use the browser to Follow two camera-available Descenders, then Return to Auto."
}

if (-not $UnrealProcess.WaitForExit(600000)) { Stop-Process -Id $UnrealProcess.Id -Force; throw "Unreal spectator consumer timed out." }
if (-not $ProducerProcess.WaitForExit(120000)) { Stop-Process -Id $ProducerProcess.Id -Force; throw "Spectator producer timed out." }
if ($null -ne $ProducerProcess.ExitCode -and $ProducerProcess.ExitCode -ne 0) { Get-Content $ProducerStderr; Get-Content $ProducerStdout; throw "Spectator producer failed with exit code $($ProducerProcess.ExitCode)." }

$RequiredOutputs = @($LiveResult, $BridgeDebug, $SchedulerDebug, $ProducerDebug, $CameraDebug, $ChannelDebug, $FocusLedger, $ViewerState, $ViewerDebug)
if (@($RequiredOutputs | Where-Object { -not (Test-Path $_) }).Count -gt 0) { throw "Spectator validation left incomplete diagnostics. Unreal exit: $($UnrealProcess.ExitCode)" }
if ((Get-Item $LiveResult).LastWriteTimeUtc -lt $ValidationStarted.AddSeconds(-1)) { throw "Unreal left stale spectator result metadata." }

$Bridge = Get-Content $BridgeDebug -Raw | ConvertFrom-Json
$Producer = Get-Content $ProducerDebug -Raw | ConvertFrom-Json
$Camera = Get-Content $CameraDebug -Raw | ConvertFrom-Json
$Channels = Get-Content $ChannelDebug -Raw | ConvertFrom-Json
$ViewerFinal = Get-Content $ViewerState -Raw | ConvertFrom-Json
$ViewerMetrics = Get-Content $ViewerDebug -Raw | ConvertFrom-Json
$Result = Get-Content $LiveResult -Raw | ConvertFrom-Json
if ($Bridge.bootstrap_count -ne 1 -or $Bridge.environment_bootstrap_count -ne 1) { throw "Bootstrap counts regressed." }
if ($Bridge.environment_rebuild_count -ne 0 -or $Bridge.full_sequence_rebuild_count -ne 0) { throw "Viewer controls rebuilt presentation state." }
if ($Bridge.rejected_frames -ne 0 -or @($Bridge.animation_binding_errors).Count -ne 0) { throw "Live bridge rejected frames or animation bindings." }
if ($Bridge.focus_change_count -lt 4 -or $Channels.follow_requests -lt 2 -or $Channels.release_requests -lt 1) { throw "Viewer focus proof was incomplete." }
if (-not [bool]$Producer.feed_fingerprint_immutable -or -not [bool]$ViewerMetrics.feed_fingerprint_immutable) { throw "Viewer activity mutated simulation truth." }
if (@($Bridge.contact_validation | Where-Object { $_.planar_error_cm -gt 30 -or $_.contact_error_cm -gt 45 }).Count -ne 0) { throw "Combat contact regression." }
if (@($Bridge.terminal_validation | Where-Object { -not $_.persistent }).Count -ne 0) { throw "Terminal persistence regression." }
if ($Camera.wall_collisions -ne 0 -or $Camera.los_failures -ne 0 -or $Camera.occupancy_failures -ne 0) { throw "Live camera safety regression." }
if ($ViewerFinal.summary.fallen_descender_count -lt 1) { throw "Final viewer state did not show a Fallen Descender." }

Write-Host "Viewer state API avg/max: $([math]::Round($ViewerMetrics.average_viewer_state_latency_ms, 3)) / $([math]::Round($ViewerMetrics.maximum_viewer_state_latency_ms, 3)) ms"
Write-Host "Viewer state bytes avg/max: $([math]::Round($ViewerMetrics.average_viewer_state_payload_bytes)) / $($ViewerMetrics.maximum_viewer_state_payload_bytes)"
Write-Host "Unreal session: 1; frames: $($Bridge.incremental_frames_received); focus changes: $($Bridge.focus_change_count)"

if ($SkipRender) { Write-Host "UNDERREACH SPECTATOR VIEWER PASS - rendering skipped."; exit 0 }

Write-Host "== Render continuous viewer-controlled Unreal proof =="
$RenderStarted = [DateTime]::UtcNow
& $UnrealEditorCmd $Project $Result.level_asset -game "-LevelSequence=$($Result.sequence_object)" "-MoviePipelineConfig=$($Result.render_config_object)" -windowed "-resx=$($Result.render_width)" "-resy=$($Result.render_height)" -log -notexturestreaming -nop4
$RenderExit = $LASTEXITCODE
$Video = Get-ChildItem -Path $Result.render_output_directory -Filter "*.mp4" -File -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $Video -or $Video.LastWriteTimeUtc -lt $RenderStarted.AddSeconds(-1)) { throw "Spectator Movie Render Queue produced no fresh MP4. Exit code: $RenderExit" }
if ($RenderExit -ne 0) { Write-Warning "Unreal returned $RenderExit after producing a fresh MP4; accepting the fresh artifact over shutdown status." }
Write-Host "UNDERREACH SPECTATOR VIEWER PASS"
Write-Host "Viewer: $BaseUrl"
Write-Host "Video: $($Video.FullName)"
Write-Host "Viewer state: $ViewerState"
Write-Host "Viewer diagnostics: $ViewerDebug"
