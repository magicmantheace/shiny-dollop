param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [int]$SimulationSteps = 90,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$AcceptedBase = "316141537fd6720c5fae1101c7f0de103dbbfb09"
git merge-base --is-ancestor $AcceptedBase HEAD
if ($LASTEXITCODE -ne 0) { throw "Current branch does not descend from the accepted 28B.2 baseline." }

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
$ChannelDebug = Join-Path $Generated "feed_channels_debug.json"
$FocusLedger = Join-Path $Generated "feed_focus_ledger.json"
$Logs = Join-Path $Generated "Logs"
$UnrealLog = Join-Path $Logs "underreach-multichannel.log"
$UnrealStdout = Join-Path $Logs "underreach-multichannel-stdout.log"
$UnrealStderr = Join-Path $Logs "underreach-multichannel-stderr.log"
$ProducerStdout = Join-Path $Logs "underreach-multichannel-producer-stdout.log"
$ProducerStderr = Join-Path $Logs "underreach-multichannel-producer-stderr.log"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

foreach ($Required in @($UnrealEditorCmd, $Project, $Python, $AcceptedResult)) {
    if (-not (Test-Path $Required)) { throw "Required local validation input is missing: $Required" }
}
$Accepted = Get-Content $AcceptedResult -Raw | ConvertFrom-Json
if (-not $Accepted.level_asset -or -not $Accepted.environment_manifest) { throw "Accepted dungeon build metadata is incomplete." }

New-Item -ItemType Directory -Path $Logs -Force | Out-Null
if (Test-Path $Spool) { Remove-Item -LiteralPath $Spool -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $Spool "deliveries") -Force | Out-Null
foreach ($Path in @(
    $LiveResult, $BridgeDebug, $SchedulerDebug, $ProducerDebug, $CameraDebug,
    $ShotLedger, $ChannelDebug, $FocusLedger, $UnrealLog, $UnrealStdout,
    $UnrealStderr, $ProducerStdout, $ProducerStderr
)) {
    if (Test-Path $Path) { Remove-Item -LiteralPath $Path -Force }
}

Write-Host "== Underreach 28B.3 focused tests =="
& $Python -m pytest `
    tests/test_underreach_multichannel_feed.py `
    tests/test_underreach_live_camera.py `
    tests/test_underreach_live_bridge.py `
    -q
if ($LASTEXITCODE -ne 0) { throw "Focused multichannel Feed tests failed." }

Write-Host ""
Write-Host "== Start deterministic multi-channel Descent producer =="
$ProducerArgs = @(
    "-m", "livingworld.underreach_multichannel_demo",
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
    throw "Multi-channel producer did not emit bootstrap."
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
    throw "Multi-channel producer did not stop after Unreal consumption completed."
}
if ($ProducerProcess.ExitCode -ne 0 -or -not (Test-Path $ProducerDebug)) {
    if (Test-Path $ProducerStderr) { Get-Content $ProducerStderr }
    if (Test-Path $ProducerStdout) { Get-Content $ProducerStdout }
    throw "Multi-channel producer failed with exit code $($ProducerProcess.ExitCode)."
}

$RequiredOutputs = @($LiveResult, $BridgeDebug, $SchedulerDebug, $ProducerDebug, $CameraDebug, $ShotLedger, $ChannelDebug, $FocusLedger)
if (@($RequiredOutputs | Where-Object { -not (Test-Path $_) }).Count -gt 0) {
    Write-Host "== Relevant Unreal errors =="
    foreach ($LogPath in @($UnrealLog, $UnrealStdout, $UnrealStderr)) {
        if (Test-Path $LogPath) {
            Select-String -Path $LogPath -Pattern "LogPython: Error|Traceback|RuntimeError|Error:" -Context 2,8 | ForEach-Object { $_.ToString() }
        }
    }
    throw "Unreal multi-channel consumer left incomplete diagnostics. Exit code: $($UnrealProcess.ExitCode)"
}
if ((Get-Item $LiveResult).LastWriteTimeUtc -lt $ValidationStarted.AddSeconds(-1)) { throw "Unreal left stale multi-channel result metadata." }

$Bridge = Get-Content $BridgeDebug -Raw | ConvertFrom-Json
$Scheduler = Get-Content $SchedulerDebug -Raw | ConvertFrom-Json
$Producer = Get-Content $ProducerDebug -Raw | ConvertFrom-Json
$Camera = Get-Content $CameraDebug -Raw | ConvertFrom-Json
$Channels = Get-Content $ChannelDebug -Raw | ConvertFrom-Json
$Focus = Get-Content $FocusLedger -Raw | ConvertFrom-Json
$Result = Get-Content $LiveResult -Raw | ConvertFrom-Json

if ($Bridge.bootstrap_count -ne 1 -or $Bridge.environment_bootstrap_count -ne 1) { throw "Bootstrap/environment was not applied exactly once." }
if ($Bridge.environment_rebuild_count -ne 0 -or $Bridge.full_sequence_rebuild_count -ne 0) { throw "Focus switching rebuilt presentation state." }
if ($Bridge.incremental_frames_received -lt 8) { throw "Too few incremental frames were consumed." }
if ($Bridge.duplicate_frames -ne 2) { throw "Duplicate frame proof did not cover bootstrap-era and post-switch delivery." }
if ($Bridge.rejected_frames -ne 0 -or @($Bridge.missing_ranges).Count -ne 0) { throw "Unreal rejected or missed live frames." }
if (@($Bridge.animation_binding_errors).Count -ne 0) { throw "Live skeletal animation bindings contain errors." }
if ($Bridge.bootstrap_actor_spawn_count -ne 2 -or $Bridge.incremental_actor_spawn_count -gt 1) { throw "Focus switching respawned actors or exceeded the accepted three-actor stage." }
if ($Bridge.focus_change_count -lt 4) { throw "Unreal did not consume enough focus changes." }
if ($Bridge.terminal_actor_count -lt 1 -or @($Bridge.terminal_validation | Where-Object { -not $_.persistent }).Count -ne 0) { throw "Terminal persistence regressed." }
if (@($Bridge.contact_validation | Where-Object { $_.planar_error_cm -gt 30 -or $_.contact_error_cm -gt 45 }).Count -ne 0) { throw "Combat contact regression." }

if (-not [bool]$Producer.feed_fingerprint_immutable) { throw "Feed activity mutated authoritative simulation truth." }
if ($Producer.total_authoritative_ledger_events -ne $Producer.total_buffered_events -or $Producer.total_buffered_events -ne $Producer.total_consumed_events) { throw "Ledger counts diverged." }
if ($Producer.events_after_last_terminal -lt 1) { throw "No canonical activity continued after terminal event." }
if ($Producer.logical_channel_count -lt 4) { throw "Logical channel directory is too small." }

if ($Channels.available_channel_count -lt 4 -or $Channels.active_descender_channel_count -lt 3) { throw "Feed channel directory did not expose multiple Descenders." }
if ($Channels.follow_requests -lt 3 -or $Channels.release_requests -ne 1) { throw "Manual follow/release sequence was incomplete." }
if ($Channels.duplicate_requests_ignored -ne 1) { throw "Duplicate follow request was not ignored exactly once." }
if (@($Channels.invalid_requests).Count -lt 1) { throw "Invalid request rejection was not exercised." }
if ($Channels.auto_switches -lt 2 -or $Channels.terminal_releases -lt 1) { throw "Automatic focus did not prove initial selection and terminal release." }
if ($Channels.reconnect_focus_result -ne "passed") { throw "Feed focus reconnect restoration failed." }
if (-not [bool]$Channels.channel_freshness_monotonic) { throw "Feed freshness cursor regressed." }
if (-not [bool]$Channels.feed_fingerprint_immutable) { throw "Channel projection changed simulation fingerprint." }

$Transitions = @($Focus.transitions)
if (@($Transitions | Where-Object { $_.reason -eq "manual_switch" }).Count -lt 1) { throw "Focus ledger lacks manual A-to-B switch." }
if (@($Transitions | Where-Object { $_.reason -eq "manual_release" }).Count -ne 1) { throw "Focus ledger lacks manual release." }
if (@($Transitions | Where-Object { $_.reason -eq "auto_terminal_release" }).Count -lt 1) { throw "Focus ledger lacks automatic terminal release." }
if (@($Transitions | Where-Object { $_.request_id -and -not $_.camera_shot_id }).Count -gt 0) { throw "A requested focus transition never reached a camera shot." }

if ($Camera.shots_generated -lt 4 -or $Camera.cuts_applied -lt 4) { throw "Live camera did not generate/apply multiple shots." }
if (@($Camera.applied_modes).Count -lt 3) { throw "Live camera did not demonstrate at least three modes." }
if ($Camera.fallback_shots -ge $Camera.shots_generated) { throw "Live camera silently remained on fallback." }
if ($Camera.minimum_wall_clearance_cm -lt 80) { throw "Live camera wall clearance regression." }
if ($Camera.minimum_combat_occupancy_width -lt 0.35 -or $Camera.minimum_combat_occupancy_height -lt 0.64) { throw "Live combat occupancy regression." }
if ($Camera.reconnect_restore_result -ne "passed") { throw "Live camera reconnect recovery failed." }

Write-Host "Channels:              $($Channels.available_channel_count)"
Write-Host "Initial auto focus:     $($Channels.initial_automatic_focus)"
Write-Host "Manual sequence:        $(@($Channels.manual_follow_sequence) -join ' -> ')"
Write-Host "Focus switches:         $($Channels.successful_switches)"
Write-Host "Terminal releases:      $($Channels.terminal_releases)"
Write-Host "Unreal process/session: $($Bridge.unreal_process_id)"
Write-Host "Incremental frames:     $($Bridge.incremental_frames_received)"
Write-Host "Ledger events:          $($Producer.total_authoritative_ledger_events)"
Write-Host "Camera shots/cuts:      $($Camera.shots_generated) / $($Camera.cuts_applied)"

if ($SkipRender) {
    Write-Host "UNDERREACH MULTICHANNEL PASS - one Unreal session switched live Feed focus. Rendering skipped."
    exit 0
}

Write-Host ""
Write-Host "== Render continuous multi-channel presentation =="
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
if (-not $Video -or $Video.LastWriteTimeUtc -lt $RenderStarted.AddSeconds(-1)) { throw "Multi-channel Movie Render Queue produced no fresh MP4. Exit code: $RenderExit" }
if ($RenderExit -ne 0) { Write-Warning "Unreal returned $RenderExit after producing a fresh MP4; accepting the artifact over shutdown status." }

Write-Host "UNDERREACH MULTICHANNEL PASS"
Write-Host "Video: $($Video.FullName)"
Write-Host "Channel diagnostics: $ChannelDebug"
Write-Host "Focus ledger: $FocusLedger"
Write-Host "Camera diagnostics: $CameraDebug"
Write-Host "Bridge diagnostics: $BridgeDebug"
