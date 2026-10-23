param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [int]$SimulationSteps = 90,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generated = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated"
$Spool = Join-Path $Generated "LiveBridge"
$ConsumerScript = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\consume_underreach_live_bridge.py"
$AcceptedResult = Join-Path $Generated "unreal_build_result.json"
$LiveResult = Join-Path $Generated "live_unreal_result.json"
$BridgeDebug = Join-Path $Generated "live_bridge_debug.json"
$SchedulerDebug = Join-Path $Generated "live_scheduler_debug.json"
$ProducerDebug = Join-Path $Generated "live_producer_debug.json"
$CameraDebug = Join-Path $Generated "live_camera_debug.json"
$ShotLedger = Join-Path $Generated "live_camera_shots.json"
$Logs = Join-Path $Generated "Logs"
$UnrealLog = Join-Path $Logs "underreach-live-bridge.log"
$UnrealStdout = Join-Path $Logs "underreach-live-bridge-stdout.log"
$UnrealStderr = Join-Path $Logs "underreach-live-bridge-stderr.log"
$ProducerStdout = Join-Path $Logs "underreach-live-producer-stdout.log"
$ProducerStderr = Join-Path $Logs "underreach-live-producer-stderr.log"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $UnrealEditorCmd)) { throw "UnrealEditor-Cmd.exe not found: $UnrealEditorCmd" }
if (-not (Test-Path $Project)) { throw "Unreal project not found: $Project" }
if (-not (Test-Path $Python)) { throw "Project Python venv not found: $Python" }
if (-not (Test-Path $AcceptedResult)) { throw "Accepted dungeon build metadata is missing. Run the offline dungeon pipeline first." }

$Accepted = Get-Content $AcceptedResult -Raw | ConvertFrom-Json
if (-not $Accepted.level_asset -or -not $Accepted.environment_manifest) {
    throw "Accepted dungeon build metadata is incomplete."
}

New-Item -ItemType Directory -Path $Logs -Force | Out-Null
if (Test-Path $Spool) { Remove-Item -LiteralPath $Spool -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $Spool "deliveries") -Force | Out-Null
foreach ($Path in @($LiveResult, $BridgeDebug, $SchedulerDebug, $ProducerDebug, $CameraDebug, $ShotLedger, $UnrealLog, $UnrealStdout, $UnrealStderr, $ProducerStdout, $ProducerStderr)) {
    if (Test-Path $Path) { Remove-Item -LiteralPath $Path -Force }
}

Write-Host "== Underreach 28B.2 focused tests =="
& $Python -m pytest tests/test_underreach_live_camera.py tests/test_underreach_live_bridge.py -q
if ($LASTEXITCODE -ne 0) { throw "Focused live bridge tests failed." }

Write-Host ""
Write-Host "== Start deterministic Descent producer =="
$ProducerArgs = @(
    "-m", "livingworld.underreach_live_bridge_demo",
    "--spool", $Spool,
    "--steps", "$SimulationSteps",
    "--poll-seconds", "0.05"
)
$ProducerProcess = Start-Process `
    -FilePath $Python `
    -ArgumentList $ProducerArgs `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $ProducerStdout `
    -RedirectStandardError $ProducerStderr `
    -PassThru

$Bootstrap = Join-Path $Spool "bootstrap.json"
$Deadline = [DateTime]::UtcNow.AddSeconds(60)
while (-not (Test-Path $Bootstrap) -and [DateTime]::UtcNow -lt $Deadline) { Start-Sleep -Milliseconds 100 }
if (-not (Test-Path $Bootstrap)) {
    if (-not $ProducerProcess.HasExited) { Stop-Process -Id $ProducerProcess.Id -Force }
    if (Test-Path $ProducerStderr) { Get-Content $ProducerStderr }
    throw "Live producer did not emit bootstrap."
}

Write-Host "== Launch one persistent Unreal consumer session =="
$ValidationStarted = [DateTime]::UtcNow
$UnrealArgs = @(
    $Project,
    "-ExecutePythonScript=$ConsumerScript",
    "-unattended", "-nop4", "-nosplash",
    "-abslog=$UnrealLog"
)
$UnrealProcess = Start-Process `
    -FilePath $UnrealEditorCmd `
    -ArgumentList $UnrealArgs `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $UnrealStdout `
    -RedirectStandardError $UnrealStderr `
    -Wait `
    -PassThru

$ProducerProcess.WaitForExit(30000)
if (-not $ProducerProcess.HasExited) {
    Stop-Process -Id $ProducerProcess.Id -Force
    throw "Live producer did not stop after Unreal consumption completed."
}

if ($ProducerProcess.ExitCode -ne 0 -or -not (Test-Path $ProducerDebug)) {
    if (Test-Path $ProducerStderr) { Get-Content $ProducerStderr }
    if (Test-Path $ProducerStdout) { Get-Content $ProducerStdout }
    throw "Live producer failed with exit code $($ProducerProcess.ExitCode)."
}

if (-not (Test-Path $LiveResult) -or -not (Test-Path $BridgeDebug) -or -not (Test-Path $SchedulerDebug) -or -not (Test-Path $CameraDebug) -or -not (Test-Path $ShotLedger)) {
    Write-Host "== Relevant Unreal errors =="
    foreach ($LogPath in @($UnrealLog, $UnrealStdout, $UnrealStderr)) {
        if (Test-Path $LogPath) {
            Select-String -Path $LogPath -Pattern "LogPython: Error|Traceback|RuntimeError|Error:" -Context 2,8 | ForEach-Object { $_.ToString() }
        }
    }
    throw "Unreal live consumer left incomplete diagnostics. Exit code: $($UnrealProcess.ExitCode)"
}
if ((Get-Item $LiveResult).LastWriteTimeUtc -lt $ValidationStarted.AddSeconds(-1)) {
    throw "Unreal live consumer left stale result metadata."
}

$Bridge = Get-Content $BridgeDebug -Raw | ConvertFrom-Json
$Scheduler = Get-Content $SchedulerDebug -Raw | ConvertFrom-Json
$Producer = Get-Content $ProducerDebug -Raw | ConvertFrom-Json
$Camera = Get-Content $CameraDebug -Raw | ConvertFrom-Json
$Result = Get-Content $LiveResult -Raw | ConvertFrom-Json

if ($Bridge.bootstrap_count -ne 1 -or $Bridge.environment_bootstrap_count -ne 1) { throw "Bootstrap/environment was not applied exactly once." }
if ($Bridge.environment_rebuild_count -ne 0 -or $Bridge.full_sequence_rebuild_count -ne 0) { throw "Live consumer rebuilt presentation state after bootstrap." }
if ($Bridge.incremental_frames_received -lt 6) { throw "Too few incremental frames were consumed." }
if ($Bridge.duplicate_frames -ne 1) { throw "Unreal duplicate-frame idempotency proof failed." }
if ($Bridge.rejected_frames -ne 0 -or @($Bridge.missing_ranges).Count -ne 0) { throw "Unreal rejected or missed live frames." }
if (@($Bridge.animation_binding_errors).Count -ne 0) { throw "Live skeletal animation bindings contain errors." }
if ($Bridge.terminal_actor_count -lt 1 -or @($Bridge.terminal_validation | Where-Object { -not $_.persistent }).Count -ne 0) {
    throw "Live terminal persistence proof failed."
}
if ($Producer.events_after_last_terminal -lt 1) { throw "No authoritative events arrived after the terminal event." }
if ($Producer.total_authoritative_ledger_events -ne $Producer.total_buffered_events -or $Producer.total_buffered_events -ne $Producer.total_consumed_events) {
    throw "Authoritative, buffered, and consumed event counts diverged."
}
if ($Camera.shots_generated -lt 4 -or $Camera.cuts_applied -lt 4) { throw "Live camera did not generate/apply multiple shots." }
if (@($Camera.applied_modes).Count -lt 3) { throw "Live camera did not demonstrate at least three modes." }
if ($Camera.fallback_shots -ge $Camera.shots_generated) { throw "Live camera silently remained on static fallback." }
if ($Camera.minimum_wall_clearance_cm -lt 80) { throw "Live camera wall clearance regression." }
if ($Camera.minimum_combat_occupancy_width -lt 0.35 -or $Camera.minimum_combat_occupancy_height -lt 0.64) {
    throw "Live combat camera occupancy regression."
}
if ($Camera.reconnect_restore_result -ne "passed") { throw "Live camera reconnect recovery failed." }

Write-Host "Unreal process/session: $($Bridge.unreal_process_id)"
Write-Host "Incremental frames:    $($Bridge.incremental_frames_received)"
Write-Host "Ledger events:         $($Producer.total_authoritative_ledger_events)"
Write-Host "Commands:              $($Bridge.applied_command_count)"
Write-Host "Terminal actors:       $($Bridge.terminal_actor_count)"
Write-Host "Events after terminal: $($Producer.events_after_last_terminal)"
Write-Host "Command digest:        $($Scheduler.command_stream_digest)"
Write-Host "Camera shots/cuts:     $($Camera.shots_generated) / $($Camera.cuts_applied)"
Write-Host "Camera modes:          $(@($Camera.applied_modes) -join ', ')"
Write-Host "Camera digest:         $($Camera.command_digest)"

if ($SkipRender) {
    Write-Host "UNDERREACH LIVE CAMERA PASS - one Unreal session consumed many incremental frames. Rendering skipped."
    exit 0
}

Write-Host ""
Write-Host "== Render incrementally assembled live presentation =="
$RenderStarted = [DateTime]::UtcNow
& $UnrealEditorCmd `
    $Project `
    $Result.level_asset `
    -game `
    "-LevelSequence=$($Result.sequence_object)" `
    "-MoviePipelineConfig=$($Result.render_config_object)" `
    -windowed `
    "-resx=$($Result.render_width)" `
    "-resy=$($Result.render_height)" `
    -log `
    -notexturestreaming `
    -nop4
$RenderExit = $LASTEXITCODE

$Video = Get-ChildItem -Path $Result.render_output_directory -Filter "*.mp4" -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $Video -or $Video.LastWriteTimeUtc -lt $RenderStarted.AddSeconds(-1)) {
    throw "Live Movie Render Queue produced no fresh MP4. Exit code: $RenderExit"
}
if ($RenderExit -ne 0) {
    Write-Warning "Unreal returned $RenderExit after producing a fresh live MP4; accepting the artifact over shutdown status."
}

Write-Host "UNDERREACH LIVE CAMERA PASS"
Write-Host "Video: $($Video.FullName)"
Write-Host "Bridge diagnostics: $BridgeDebug"
Write-Host "Scheduler diagnostics: $SchedulerDebug"
Write-Host "Camera diagnostics: $CameraDebug"
Write-Host "Shot ledger: $ShotLedger"
