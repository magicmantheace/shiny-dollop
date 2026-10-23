$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-local-video-enhancement-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_10"
$Proof = Join-Path $Out "local-video-enhancement-proof.json"
$Repro = Join-Path $Out "local-video-enhancement-proof-repro.json"
$Seed = "underreach-30-5-10-local-video-enhancement-proof"

Write-Host "[30.5.10] Accepted 30A.1-30.5.9 regressions + focused local-video/GPU-scheduler tests"
& $Python -m pytest -q `
  tests/test_underreach_30a1_descent_run_state.py `
  tests/test_underreach_30a2_multi_stratum_progression.py `
  tests/test_underreach_30a3_loot_cache_relic.py `
  tests/test_underreach_30a4_resources_survival.py `
  tests/test_underreach_30a5_full_autonomous_descent.py `
  tests/test_underreach_30b1_ai_brain_foundation.py `
  tests/test_underreach_30b2_intent_validation_execution_bridge.py `
  tests/test_underreach_30b3_brain_driven_descent_orchestration.py `
  tests/test_underreach_30c1_social_state_foundation.py `
  tests/test_underreach_30c2_social_memory_relationship_evolution.py `
  tests/test_underreach_30c3_social_intent_interaction_execution.py `
  tests/test_underreach_30c4_parties_alliances_leadership.py `
  tests/test_underreach_30c5_rivalry_betrayal_social_conflict.py `
  tests/test_underreach_30c6_group_decision_autonomous_social_orchestration.py `
  tests/test_underreach_30c6_alliance_conflict_direction.py `
  tests/test_underreach_30_5_1_canonical_media_event_export.py `
  tests/test_underreach_30_5_2_media_db_durable_queue_provider_router.py `
  tests/test_underreach_30_5_3_highlight_story_arc_detection.py `
  tests/test_underreach_30_5_4_delver_chronicle_profile_system.py `
  tests/test_underreach_30_5_4_terminal_archive_only.py `
  tests/test_underreach_30_5_5_narrative_claim_manifest_fact_verification.py `
  tests/test_underreach_30_5_6_presentation_identity_system.py `
  tests/test_underreach_30_5_7_headless_local_image_production.py `
  tests/test_underreach_30_5_8_narration_captions_audio.py `
  tests/test_underreach_30_5_9_automated_ffmpeg_motion_story_production.py `
  tests/test_underreach_30_5_10_local_video_enhancement_gpu_scheduling.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.10] Verifying local FFmpeg/ffprobe acceptance backend"
$FfmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$FfprobeCommand = Get-Command ffprobe -ErrorAction SilentlyContinue
if ($null -eq $FfmpegCommand) { throw "30.5.10 acceptance backend requires local ffmpeg on PATH" }
if ($null -eq $FfprobeCommand) { throw "30.5.10 acceptance backend requires local ffprobe on PATH" }
$EncoderText = (& ffmpeg -hide_banner -encoders 2>&1 | Out-String)
if ($EncoderText -notmatch "libx264") { throw "30.5.10 acceptance backend requires FFmpeg libx264" }

$Source = Get-Content -Raw (Join-Path $RepoRoot "src\livingworld\underreach_local_video_enhancement.py")
if ($Source -match "from\s+\.crawl_" -or $Source -match "from\s+\.underreach_brain") {
    throw "30.5.10 production module imported canonical simulation services"
}
if ($Source -match "import\s+requests" -or $Source -match "import\s+httpx" -or $Source -match "from\s+openai") {
    throw "30.5.10 production module introduced required network/cloud client"
}
if ($Source -notmatch "ProviderKind\.VIDEO" -or $Source -notmatch "image_to_video_required=True") {
    throw "30.5.10 lost capability-routed VIDEO/I2V contract"
}
if ($Source -notmatch "motion_story_fallback_guaranteed" -or $Source -notmatch "gpu_budget_exhausted") {
    throw "30.5.10 lost fallback or GPU-budget contract"
}

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.10] Running deterministic file-backed local-video/GPU proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.local-video-enhancement-proof.v1") { throw "30.5.10 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.local-video-enhancement.v1") { throw "30.5.10 slice protocol changed" }
if ($P.implementation_version -ne "30.5.10") { throw "30.5.10 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.10 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.10 snapshot reproducibility mismatch" }
if ($P.media.job_digest -ne $Q.media.job_digest) { throw "30.5.10 job reproducibility mismatch" }
if ($P.media.artifact_digest -ne $Q.media.artifact_digest) { throw "30.5.10 artifact reproducibility mismatch" }
if ($P.media.provider_execution_digest -ne $Q.media.provider_execution_digest) { throw "30.5.10 provider execution reproducibility mismatch" }
if ($P.scheduler.reservation_digest -ne $Q.scheduler.reservation_digest) { throw "30.5.10 GPU reservation reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.10 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.10 presentation gained simulation authority" }
if ($A.unreal_dependency -ne $false) { throw "30.5.10 introduced Unreal dependency" }
if ($A.required_cloud_api -ne $false -or $A.required_paid_provider -ne $false) { throw "30.5.10 added required cloud/paid dependency" }
if ($A.motion_story_fallback_guaranteed -ne $true) { throw "30.5.10 lost motion-story fallback guarantee" }
if ($P.canonical.unchanged_during_video_enhancement -ne $true) { throw "30.5.10 video enhancement changed canonical Crawl/Ledger truth" }

$S = $P.selection
if ($S.eligible -ne $true -or [int]$S.highlight_score -ne 97) { throw "30.5.10 cinematic source eligibility changed" }
if ($S.treatment -ne "cinematic_priority" -or [int]$S.selected_shot_count -ne 3) { throw "30.5.10 cinematic shot-selection policy changed" }
if (($S.shot_indexes -join ",") -ne "0,1,2") { throw "30.5.10 deterministic shot ordering changed" }
if (($S.durations_ms | Where-Object { [int]$_ -ne 3000 }).Count -ne 0) { throw "30.5.10 short-shot duration policy changed" }

$V = $P.production
if ([int]$V.completed_count -ne 3) { throw "30.5.10 did not complete three cinematic enhancement shots" }
if ([int]$V.video_artifact_count -ne 3 -or [int]$V.sidecar_artifact_count -ne 3) { throw "30.5.10 enhancement artifact counts changed" }
if ($V.output_files_exist -ne $true -or $V.fallback_still_exists -ne $true) { throw "30.5.10 local clips or motion-story fallback missing" }
if ($V.provider_local -ne $true -or [int]$V.provider_execution_count -ne 3) { throw "30.5.10 acceptance proof did not remain local" }

$R = $P.restart
if ([int]$R.recovered_media_jobs -ne 1 -or [int]$R.recovered_gpu_locks -ne 1) { throw "30.5.10 restart recovery count changed" }
if ($R.same_first_job -ne $true -or [int]$R.first_attempt_count -ne 2) { throw "30.5.10 restart did not recover same video job on attempt 2" }
if ($R.gpu_lock_clear -ne $true) { throw "30.5.10 GPU serialization lock remained stuck after recovery" }

$G = $P.scheduler
if ($G.serialized_gpu_work -ne $true) { throw "30.5.10 GPU work is no longer serialized" }
if ([int64]$G.max_gpu_ms_per_window -ne 36000) { throw "30.5.10 proof GPU budget changed" }
if ([int]$G.max_retries_per_shot -ne 2) { throw "30.5.10 retry policy changed" }
if ([int]$G.reservation_count -ne 3 -or $G.all_completed -ne $true) { throw "30.5.10 GPU reservations did not complete cleanly" }

$I = $P.idempotency
if ($I.repeat_same_job_ids -ne $true -or $I.snapshot_equal_after_repeat -ne $true) { throw "30.5.10 completed re-enqueue duplicated media/GPU state" }

$B = $P.budget
if ($B.fallback_exists -ne $true -or $B.job_held -ne $true) { throw "30.5.10 exhausted GPU budget did not degrade to fallback" }
if ($B.reason_code -ne "gpu_budget_exhausted" -or [int]$B.reservation_count -ne 0) { throw "30.5.10 exhausted-budget hold/reservation behavior changed" }

$F = $P.failure
if (($F.statuses -join ",") -ne "retry,retry,failed") { throw "30.5.10 bounded video retry sequence changed" }
if ([int]$F.attempt_count -ne 3 -or $F.final_failed -ne $true) { throw "30.5.10 video failure did not stop after two retries" }
if ($F.fallback_exists -ne $true -or $F.fallback_retained_each_attempt -ne $true) { throw "30.5.10 video failure lost motion-story fallback" }
if ([int]$F.provider_execution_count -ne 3 -or $F.gpu_lock_clear -ne $true) { throw "30.5.10 failure accounting/serialization changed" }

$PRoute = $P.routing
if ($PRoute.paid_blocked_by_default -ne $true) { throw "30.5.10 paid video provider was not blocked by default" }
if ($PRoute.paid_selected_with_all_gates -ne $true) { throw "30.5.10 explicit paid routing probe failed" }
if ($PRoute.sixteen_gb_provider_blocked -ne $true) { throw "30.5.10 16 GB provider escaped the 12 GB policy" }

$M = $P.media
if ([int]$M.job_count -ne 3) { throw "30.5.10 enhancement job count changed" }
if ([int]$M.artifact_count -ne 6) { throw "30.5.10 enhancement artifact count changed" }
if ([int]$M.provider_execution_count -ne 3) { throw "30.5.10 provider execution count changed" }

Write-Host "[30.5.10] Local video enhancement & GPU scheduling proof PASS"
Write-Host "digest=$($P.digest) jobs=$($M.job_count) clips=$($V.video_artifact_count) reservations=$($G.reservation_count)"
Write-Host "restartAttempts=$($R.first_attempt_count) fallback=$($A.motion_story_fallback_guaranteed) canonicalUnchanged=$($P.canonical.unchanged_during_video_enhancement)"

Write-Host "[30.5.10] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.10] PASS"
Write-Host "Proof: $Proof"
