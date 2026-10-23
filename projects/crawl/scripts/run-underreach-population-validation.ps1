param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [int]$SimulationSteps = 18,
    [int]$ViewerPort = 8013,
    [switch]$SkipBlender,
    [switch]$SkipImport,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$AcceptedBase = "ddaa19ccd673b1e3baedb0d2b68377e8f03208b9"
git merge-base --is-ancestor $AcceptedBase HEAD
if ($LASTEXITCODE -ne 0) { throw "Current branch does not descend from the accepted 29A.1.1 baseline." }

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Npm = "C:\Program Files\nodejs\npm.cmd"
$Viewer = Join-Path $RepoRoot "viewer"
$ViewerDist = Join-Path $Viewer "dist"
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generated = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated"
$Generated29A2 = Join-Path $Generated "29a2"
$Spool = Join-Path $Generated "LiveBridge"
$ConsumerScript = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\consume_underreach_live_bridge.py"
$LiveResult = Join-Path $Generated "live_unreal_result.json"
$BridgeDebug = Join-Path $Generated "live_bridge_debug.json"
$ProducerDebug = Join-Path $Generated "live_producer_debug.json"
$CameraDebug = Join-Path $Generated "live_camera_debug.json"
$ChannelDebug = Join-Path $Generated "feed_channels_debug.json"
$FocusLedger = Join-Path $Generated "feed_focus_ledger.json"
$ViewerState = Join-Path $Generated "viewer_state_snapshot.json"
$ViewerDebug = Join-Path $Generated "viewer_debug.json"
$PopulationDebug = Join-Path $Generated29A2 "population_debug.json"
$DiversityReport = Join-Path $Generated29A2 "diversity_report.json"
$ReconstructionReport = Join-Path $Generated29A2 "reconstruction_report.json"
$PerformanceReport = Join-Path $Generated29A2 "performance_report.json"
$LivePopulationReport = Join-Path $Generated29A2 "live_population_report.json"
$ValidationReport = Join-Path $Generated29A2 "validation_report.json"
$CameraAcquisition = Join-Path $Generated29A2 "camera_acquisition_debug.json"
$Logs = Join-Path $Generated "Logs"
$UnrealLog = Join-Path $Logs "underreach-29a2-population.log"
$UnrealStdout = Join-Path $Logs "underreach-29a2-population-stdout.log"
$UnrealStderr = Join-Path $Logs "underreach-29a2-population-stderr.log"
$ProducerStdout = Join-Path $Logs "underreach-29a2-producer-stdout.log"
$ProducerStderr = Join-Path $Logs "underreach-29a2-producer-stderr.log"
$BaseUrl = "http://127.0.0.1:$ViewerPort"

foreach ($Required in @($UnrealEditorCmd, $Project, $Python, $Npm)) {
    if (-not (Test-Path $Required)) { throw "Required local 29A.2 input is missing: $Required" }
}

Write-Host "== Underreach 29A.2 deterministic population diagnostics =="
& $Python scripts/generate-underreach-population-diagnostics.py --output $Generated29A2
if ($LASTEXITCODE -ne 0) { throw "29A.2 population diagnostics failed." }

Write-Host "== Underreach 29A.2 focused and live regression tests =="
& $Python -m pytest tests/test_underreach_29a2_population.py tests/test_character_dna.py tests/test_underreach_live_bridge.py tests/test_underreach_live_camera.py tests/test_underreach_multichannel_feed.py tests/test_underreach_spectator_viewer.py -q
if ($LASTEXITCODE -ne 0) { throw "29A.2 focused/regression tests failed." }

Write-Host "== Underreach viewer tests and production build =="
Push-Location $Viewer
try {
    & $Npm test
    if ($LASTEXITCODE -ne 0) { throw "Viewer frontend tests failed." }
    & $Npm run build
    if ($LASTEXITCODE -ne 0) { throw "Viewer production build failed." }
} finally { Pop-Location }

if (-not $SkipBlender) {
    Write-Host "== Rebuild six deterministic MPFB visual archetypes =="
    & (Join-Path $PSScriptRoot "build-underreach-mpfb-descenders.ps1")
    if ($LASTEXITCODE -ne 0) { throw "29A.2 MPFB/Blender build failed." }
}

if (-not $SkipImport) {
    Write-Host "== Import six visual archetypes into Unreal =="
    $ImportReport = Join-Path $Generated "29a1\unreal_character_import_report.json"
    $ImportStarted = [DateTime]::UtcNow
    & $UnrealEditorCmd $Project -run=pythonscript "-script=$RepoRoot\unreal\CrawlPresentation\Content\Python\import_underreach_characters.py" -unattended -nop4 -nosplash -NullRHI -log
    if (-not (Test-Path $ImportReport) -or (Get-Item $ImportReport).LastWriteTimeUtc -lt $ImportStarted.AddSeconds(-1)) {
        throw "29A.2 Unreal character import left stale metadata (exit $LASTEXITCODE)."
    }
}

New-Item -ItemType Directory -Path $Logs -Force | Out-Null
if (Test-Path $Spool) { Remove-Item -LiteralPath $Spool -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $Spool "deliveries") -Force | Out-Null
foreach ($Path in @(
    $LiveResult, $BridgeDebug, $ProducerDebug, $CameraDebug, $ChannelDebug,
    $FocusLedger, $ViewerState, $ViewerDebug, $LivePopulationReport,
    $ValidationReport, $CameraAcquisition, $UnrealLog, $UnrealStdout,
    $UnrealStderr, $ProducerStdout, $ProducerStderr
)) {
    if (Test-Path $Path) { Remove-Item -LiteralPath $Path -Force }
}

Write-Host "== Start 10-Descender population, Feed, and persistent Unreal consumer =="
$ProducerArgs = @(
    "-m", "livingworld.underreach_multichannel_demo",
    "--spool", $Spool,
    "--steps", "$SimulationSteps",
    "--poll-seconds", "0.55",
    "--external-controls",
    "--population-proof",
    "--viewer-host", "127.0.0.1",
    "--viewer-port", "$ViewerPort",
    "--viewer-static-directory", $ViewerDist,
    "--viewer-hold-seconds", "30"
)
$ProducerProcess = Start-Process -FilePath $Python -ArgumentList $ProducerArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $ProducerStdout -RedirectStandardError $ProducerStderr -PassThru
$UnrealProcess = $null
try {
    $Bootstrap = Join-Path $Spool "bootstrap.json"
    $Deadline = [DateTime]::UtcNow.AddSeconds(60)
    while (-not (Test-Path $Bootstrap) -and [DateTime]::UtcNow -lt $Deadline) { Start-Sleep -Milliseconds 100 }
    if (-not (Test-Path $Bootstrap)) { throw "Population producer did not emit bootstrap." }

    $BootstrapBody = Get-Content $Bootstrap -Raw | ConvertFrom-Json
    $PopulationActors = @($BootstrapBody.actors | Where-Object { $_.character_renderer_manifest })
    if ($BootstrapBody.presentation_profile -ne "29a2_population" -or $PopulationActors.Count -ne 10) {
        throw "Bootstrap is not the required 10-Descender population proof."
    }

    $ValidationStarted = [DateTime]::UtcNow
    $UnrealArgs = @($Project, "-ExecutePythonScript=$ConsumerScript", "-unattended", "-nop4", "-nosplash", "-abslog=$UnrealLog")
    $UnrealProcess = Start-Process -FilePath $UnrealEditorCmd -ArgumentList $UnrealArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $UnrealStdout -RedirectStandardError $UnrealStderr -PassThru
    [int64]$ObservedUnrealPeakWorkingSet = 0
    [int64]$ObservedUnrealPeakVirtualMemory = 0
    function Update-UnrealMemoryObservation {
        if ($null -eq $UnrealProcess -or $UnrealProcess.HasExited) { return }
        $UnrealProcess.Refresh()
        $script:ObservedUnrealPeakWorkingSet = [math]::Max($script:ObservedUnrealPeakWorkingSet, [int64]$UnrealProcess.WorkingSet64)
        $script:ObservedUnrealPeakVirtualMemory = [math]::Max($script:ObservedUnrealPeakVirtualMemory, [int64]$UnrealProcess.VirtualMemorySize64)
    }

    $Deadline = [DateTime]::UtcNow.AddSeconds(120)
    $State = $null
    while ($null -eq $State -and [DateTime]::UtcNow -lt $Deadline) {
        Update-UnrealMemoryObservation
        try { $State = Invoke-RestMethod -Uri "$BaseUrl/api/feed/viewer/state?viewer_id=viewer_local_alpha" -TimeoutSec 2 } catch { Start-Sleep -Milliseconds 250 }
    }
    if ($null -eq $State) { throw "Population viewer did not become reachable at $BaseUrl." }

    function Invoke-PopulationControl([string]$Path, [hashtable]$Body) {
        Invoke-RestMethod -Uri "$BaseUrl$Path" -Method Post -ContentType "application/json" -Body ($Body | ConvertTo-Json -Compress) -TimeoutSec 5
    }
    $FollowTargets = @("live_descender_000", "live_descender_002", "live_descender_004", "live_descender_008")
    foreach ($Target in $FollowTargets) {
        $State = Invoke-RestMethod -Uri "$BaseUrl/api/feed/viewer/state?viewer_id=viewer_local_alpha" -TimeoutSec 5
        if (-not @($State.descenders | Where-Object { $_.descender_id -eq $Target -and $_.camera_available }).Count) {
            throw "Required Follow target is not camera-available: $Target"
        }
        $Body = @{
            viewer_id = "viewer_local_alpha"
            request_id = "population_follow_$Target"
            requested_at_presentation_tick = [int]$State.focus.presentation_tick
            descender_id = $Target
        }
        [void](Invoke-PopulationControl "/api/feed/live/follow" $Body)
        Start-Sleep -Seconds 2
        Update-UnrealMemoryObservation
        $State = Invoke-RestMethod -Uri "$BaseUrl/api/feed/viewer/state?viewer_id=viewer_local_alpha" -TimeoutSec 5
        if ($State.focus.mode -ne "manual" -or $State.focus.active_descender_id -ne $Target) {
            throw "Follow did not acquire $Target."
        }
    }
    $State = Invoke-RestMethod -Uri "$BaseUrl/api/feed/viewer/state?viewer_id=viewer_local_alpha" -TimeoutSec 5
    $Release = @{
        viewer_id = "viewer_local_alpha"
        request_id = "population_return_auto"
        requested_at_presentation_tick = [int]$State.focus.presentation_tick
    }
    [void](Invoke-PopulationControl "/api/feed/live/release" $Release)
    Write-Host "Follow proof acknowledged: $($FollowTargets -join ', ') -> Auto"

    $UnrealDeadline = [DateTime]::UtcNow.AddSeconds(900)
    while (-not $UnrealProcess.HasExited -and [DateTime]::UtcNow -lt $UnrealDeadline) {
        Update-UnrealMemoryObservation
        Start-Sleep -Milliseconds 250
    }
    if (-not $UnrealProcess.HasExited) { Stop-Process -Id $UnrealProcess.Id -Force; throw "Unreal population consumer timed out." }
    if (-not $ProducerProcess.WaitForExit(180000)) { Stop-Process -Id $ProducerProcess.Id -Force; throw "Population producer timed out." }
    if ($null -ne $ProducerProcess.ExitCode -and $ProducerProcess.ExitCode -ne 0) {
        Get-Content $ProducerStderr; Get-Content $ProducerStdout
        throw "Population producer failed with exit code $($ProducerProcess.ExitCode)."
    }

    # Capture process-level cost after the persistent session exits. These are
    # observed peaks for the whole Unreal validation process, not an invented
    # incremental-only memory figure.
    $PerformanceBody = Get-Content $PerformanceReport -Raw | ConvertFrom-Json
    $PerformanceBody | Add-Member -NotePropertyName unreal_observed_peak_working_set_bytes -NotePropertyValue $ObservedUnrealPeakWorkingSet -Force
    $PerformanceBody | Add-Member -NotePropertyName unreal_observed_peak_virtual_memory_bytes -NotePropertyValue $ObservedUnrealPeakVirtualMemory -Force
    $PerformanceBody | Add-Member -NotePropertyName unreal_observed_peak_working_set_mb -NotePropertyValue ([math]::Round($ObservedUnrealPeakWorkingSet / 1MB, 3)) -Force
    $PerformanceBody | Add-Member -NotePropertyName gross_unreal_peak_working_set_bytes_per_live_actor -NotePropertyValue ([math]::Round($ObservedUnrealPeakWorkingSet / 10, 2)) -Force
    $PerformanceBody | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $PerformanceReport -Encoding utf8

    $RequiredOutputs = @(
        $LiveResult, $BridgeDebug, $ProducerDebug, $CameraDebug, $ChannelDebug,
        $FocusLedger, $ViewerState, $ViewerDebug, $PopulationDebug,
        $DiversityReport, $ReconstructionReport, $PerformanceReport,
        $LivePopulationReport, $ValidationReport, $CameraAcquisition
    )
    $Missing = @($RequiredOutputs | Where-Object { -not (Test-Path $_) })
    if ($Missing.Count) { throw "Population validation left incomplete diagnostics: $($Missing -join ', ')" }
    if ((Get-Item $LiveResult).LastWriteTimeUtc -lt $ValidationStarted.AddSeconds(-1)) {
        throw "Unreal left stale population result metadata."
    }

    $Bridge = Get-Content $BridgeDebug -Raw | ConvertFrom-Json
    $Producer = Get-Content $ProducerDebug -Raw | ConvertFrom-Json
    $Camera = Get-Content $CameraDebug -Raw | ConvertFrom-Json
    $Channels = Get-Content $ChannelDebug -Raw | ConvertFrom-Json
    $ViewerFinal = Get-Content $ViewerState -Raw | ConvertFrom-Json
    $ViewerMetrics = Get-Content $ViewerDebug -Raw | ConvertFrom-Json
    $Population = Get-Content $PopulationDebug -Raw | ConvertFrom-Json
    $Diversity = Get-Content $DiversityReport -Raw | ConvertFrom-Json
    $Reconstruction = Get-Content $ReconstructionReport -Raw | ConvertFrom-Json
    $LivePopulation = Get-Content $LivePopulationReport -Raw | ConvertFrom-Json
    $Validation = Get-Content $ValidationReport -Raw | ConvertFrom-Json
    $Acquisition = Get-Content $CameraAcquisition -Raw | ConvertFrom-Json
    $Result = Get-Content $LiveResult -Raw | ConvertFrom-Json

    if (-not [bool]$Producer.population_proof -or $Producer.presented_descender_count -ne 10) { throw "Producer population fixture regressed." }
    if ($LivePopulation.simultaneously_presentable_count -ne 10 -or $LivePopulation.species_counts.human -ne 6 -or $LivePopulation.species_counts.dwarf -ne 4) { throw "Live species/count validation failed." }
    if ($LivePopulation.visual_variant_count -lt 6 -or $LivePopulation.visual_identity_count -ne 10) { throw "Live identities are not sufficiently distinct." }
    if (-not $LivePopulation.assembly.one_body_per_actor -or -not $LivePopulation.assembly.species_switch_exclusive) { throw "Body/species assembly is not exclusive." }
    if (-not $LivePopulation.assembly.all_material_slots_bound -or $LivePopulation.runtime_material_asset_count -lt 20) { throw "Runtime population material diversity is incomplete." }
    if (-not $LivePopulation.equipment.valid -or $LivePopulation.equipment.duplicate_visible_equipment_count -ne 0) { throw "Equipment attachment regression." }
    if ($LivePopulation.facing.count_above_45_degrees -ne 0 -or -not $LivePopulation.facing.attacks_aligned) { throw "Facing regression." }
    if (@($Bridge.animation_binding_errors).Count -ne 0 -or $Bridge.rejected_frames -ne 0) { throw "Animation/bridge regression." }
    if (@($Bridge.contact_validation | Where-Object { $_.planar_error_cm -gt 30 -or $_.contact_error_cm -gt 45 }).Count -ne 0) { throw "Combat contact regression." }
    if (@($Bridge.terminal_validation | Where-Object { -not $_.persistent }).Count -ne 0) { throw "Terminal persistence regression." }
    if ($Camera.wall_collisions -ne 0 -or $Camera.los_failures -ne 0 -or $Camera.occupancy_failures -ne 0) { throw "Camera geometry/LOS/occupancy regression." }
    if ($Acquisition.maximum_empty_view_duration_seconds -gt 2.0 -or $Acquisition.stale_target_incidents -ne 0 -or @($Acquisition.missing_focus_transition_ids).Count -ne 0) { throw "Follow/camera acquisition regression." }
    if (-not $Validation.equipment_valid -or -not $Validation.facing_valid -or -not $Validation.camera_acquisition_valid -or -not $Validation.anatomy_valid -or -not $Validation.species_switch_exclusive) { throw "29A.2 validation report failed." }
    if ($Diversity.exact_dna_duplicate_count -ne 0 -or $Diversity.exact_renderer_manifest_duplicate_count -ne 0) { throw "Clone-avoidance metrics failed." }
    if (-not $Reconstruction.all_identity_fields_equal -or -not $Reconstruction.canonical_fingerprint_equal -or -not $Reconstruction.channel_mapping_equal -or -not $Reconstruction.population_digest_equal) { throw "Checkpoint/reconstruction equality failed." }
    if ($Reconstruction.ledger_duplicate_canonical_events -ne 0 -or $Reconstruction.ledger_skipped_canonical_events -ne 0) { throw "Canonical Ledger continuity failed." }
    if (-not [bool]$Producer.feed_fingerprint_immutable -or -not [bool]$ViewerMetrics.feed_fingerprint_immutable) { throw "Presentation mutated simulation truth." }
    if ($Result.render_width -ne 1920 -or $Result.render_height -ne 1080 -or $Result.render_fps -ne 60) { throw "Population render settings regressed." }
    if ($Result.presentation_duration_seconds -lt 90 -or $Result.presentation_duration_seconds -gt 180) { throw "Population proof duration is outside 90-180 seconds: $($Result.presentation_duration_seconds)" }

    Write-Host "Live population: 6 Human + 4 Dwarf; 10 identities; $($LivePopulation.visual_variant_count) archetypes"
    Write-Host "Follow/Auto: $($FollowTargets -join ', ') -> Auto; max empty view $($Acquisition.maximum_empty_view_duration_seconds)s"
    Write-Host "Presentation: $([math]::Round($Result.presentation_duration_seconds, 2))s at 1920x1080/60fps"

    if ($SkipRender) { Write-Host "UNDERREACH 29A.2 POPULATION PASS - rendering skipped."; exit 0 }

    Write-Host "== Render fresh Underreach 29A.2 population proof =="
    $RenderStarted = [DateTime]::UtcNow
    & $UnrealEditorCmd $Project $Result.level_asset -game "-LevelSequence=$($Result.sequence_object)" "-MoviePipelineConfig=$($Result.render_config_object)" -windowed "-resx=$($Result.render_width)" "-resy=$($Result.render_height)" -log -notexturestreaming -nop4
    $RenderExit = $LASTEXITCODE
    $Video = Get-ChildItem -Path $Result.render_output_directory -Filter "*.mp4" -File -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if (-not $Video -or $Video.LastWriteTimeUtc -lt $RenderStarted.AddSeconds(-1)) { throw "Population Movie Render Queue produced no fresh MP4. Exit code: $RenderExit" }
    if ($RenderExit -ne 0) { Write-Warning "Unreal returned $RenderExit after producing a fresh MP4; accepting the fresh artifact over shutdown status." }
    Write-Host "UNDERREACH 29A.2 POPULATION PASS"
    Write-Host "Video: $($Video.FullName)"
    Write-Host "Live population: $LivePopulationReport"
    Write-Host "Diagnostics: $Generated29A2"
} finally {
    if ($null -ne $UnrealProcess -and -not $UnrealProcess.HasExited) { Stop-Process -Id $UnrealProcess.Id -Force -ErrorAction SilentlyContinue }
    if ($null -ne $ProducerProcess -and -not $ProducerProcess.HasExited) { Stop-Process -Id $ProducerProcess.Id -Force -ErrorAction SilentlyContinue }
}
