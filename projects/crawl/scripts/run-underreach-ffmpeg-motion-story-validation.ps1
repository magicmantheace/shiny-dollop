$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-ffmpeg-motion-story-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_9"
$Proof = Join-Path $Out "ffmpeg-motion-story-proof.json"
$Repro = Join-Path $Out "ffmpeg-motion-story-proof-repro.json"
$Seed = "underreach-30-5-9-ffmpeg-motion-story-proof"

Write-Host "[30.5.9] Accepted 30A.1-30.5.8 regressions + focused FFmpeg motion-story tests"
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
  tests/test_underreach_30_5_9_automated_ffmpeg_motion_story_production.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.9] Verifying required local FFmpeg capabilities"
$FfmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$FfprobeCommand = Get-Command ffprobe -ErrorAction SilentlyContinue
if ($null -eq $FfmpegCommand) { throw "30.5.9 requires local ffmpeg on PATH" }
if ($null -eq $FfprobeCommand) { throw "30.5.9 requires local ffprobe on PATH" }

$FilterText = (& ffmpeg -hide_banner -filters 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "30.5.9 could not query FFmpeg filters" }
foreach ($RequiredFilter in @("subtitles", "xfade", "zoompan", "fade", "loudnorm", "sidechaincompress", "amix")) {
  if ($FilterText -notmatch [regex]::Escape($RequiredFilter)) {
    throw "30.5.9 local FFmpeg is missing required filter: $RequiredFilter"
  }
}

$EncoderText = (& ffmpeg -hide_banner -encoders 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "30.5.9 could not query FFmpeg encoders" }
if ($EncoderText -notmatch "libx264") { throw "30.5.9 local FFmpeg is missing required libx264 encoder" }

$ProbeVersion = (& ffprobe -version 2>&1 | Select-Object -First 1 | Out-String).Trim()
if (-not $ProbeVersion) { throw "30.5.9 ffprobe version probe failed" }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.9] Running real deterministic-plan FFmpeg motion-story proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.ffmpeg-motion-story-proof.v1") { throw "30.5.9 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.ffmpeg-motion-story.v1") { throw "30.5.9 slice protocol changed" }
if ($P.implementation_version -ne "30.5.9") { throw "30.5.9 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.9 semantic proof reproducibility digest mismatch" }
if ($P.media.job_digest -ne $Q.media.job_digest) { throw "30.5.9 durable motion-job reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.9 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.9 presentation gained simulation authority" }
if ($A.unreal_dependency -ne $false) { throw "30.5.9 introduced Unreal dependency" }
if ($A.video_model_dependency -ne $false -or $A.video_diffusion_used -ne $false) { throw "30.5.9 introduced video-model dependency" }
if ($A.required_cloud_api -ne $false -or $A.required_paid_provider -ne $false) { throw "30.5.9 added required cloud/paid dependency" }
if ($A.guaranteed_motion_story_fallback -ne $true) { throw "30.5.9 lost guaranteed motion-story fallback" }
if ($P.canonical.unchanged_during_motion_story_production -ne $true) { throw "30.5.9 changed canonical Crawl/Ledger truth" }

$Input = $P.inputs
if ([int]$Input.scene_image_count -ne 2) { throw "30.5.9 proof scene-image input count changed" }
if ($Input.verified_review_ready -ne $true) { throw "30.5.9 proof narration was not REVIEW_READY" }
if (@($Input.source_event_ids).Count -lt 1 -or @($Input.source_envelope_ids).Count -lt 1) { throw "30.5.9 lost canonical media provenance" }
if ($Input.music_asset_resolved -ne $true) { throw "30.5.9 narrated proof did not resolve local royalty-safe music" }

$N = $P.narrated
if ($N.completed -ne $true -or $N.mp4_exists -ne $true -or $N.mp4_signature -ne $true) { throw "30.5.9 narrated MP4 was not produced" }
if ([int]$N.width -ne 360 -or [int]$N.height -ne 640) { throw "30.5.9 narrated proof is not 9:16" }
if ($N.audio_stream_present -ne $true) { throw "30.5.9 narrated MP4 lost audio stream" }
if ($N.captions_burned -ne $true -or $N.narration_mode -ne "narrated") { throw "30.5.9 narrated caption mode changed" }
if ($N.loudness_normalization -ne $true -or $N.music_ducking -ne $true -or $N.audio_fades -ne $true -or $N.audio_mixing -ne $true) { throw "30.5.9 narrated FFmpeg audio processing changed" }
if ($N.video_model_dependency -ne $false) { throw "30.5.9 narrated path gained a video model" }
if ($N.ffmpeg_provider_id -ne "local_ffmpeg" -or -not $N.ffmpeg_command_plan_digest) { throw "30.5.9 narrated path lost FFmpeg provenance" }

$C = $P.caption_only
if ($C.completed -ne $true -or $C.mp4_exists -ne $true -or $C.mp4_signature -ne $true) { throw "30.5.9 caption-only MP4 was not produced" }
if ([int]$C.width -ne 360 -or [int]$C.height -ne 640) { throw "30.5.9 caption-only proof is not 9:16" }
if ($C.audio_stream_present -ne $false) { throw "30.5.9 caption-only MP4 unexpectedly contains audio" }
if ($C.captions_burned -ne $true -or $C.narration_mode -ne "caption_only") { throw "30.5.9 caption-only mode changed" }
if ($C.video_model_dependency -ne $false -or $C.ffmpeg_provider_id -ne "local_ffmpeg") { throw "30.5.9 caption-only path escaped local FFmpeg fallback" }

$R = $P.restart
if ([int]$R.recovered_count -ne 1 -or $R.same_job -ne $true) { throw "30.5.9 restart did not recover same motion-story job" }
if ([int]$R.attempt_count -ne 2 -or $R.completed -ne $true) { throw "30.5.9 restart retry/complete contract changed" }

$I = $P.idempotency
if ($I.repeat_same_job -ne $true) { throw "30.5.9 completed repeat enqueue changed durable job identity" }
if ($I.snapshot_equal_after_repeat -ne $true) { throw "30.5.9 completed repeat enqueue duplicated media state" }

$M = $P.media
if ([int]$M.job_count -ne 2) { throw "30.5.9 motion-story job count changed" }
if ([int]$M.artifact_count -ne 6) { throw "30.5.9 motion-story artifact count changed" }
if ([int]$M.provider_execution_count -ne 2) { throw "30.5.9 FFmpeg execution count changed" }

Write-Host "[30.5.9] FFmpeg motion-story proof PASS"
Write-Host "digest=$($P.digest) jobs=$($M.job_count) artifacts=$($M.artifact_count) executions=$($M.provider_execution_count)"
Write-Host "narrated=$($N.width)x$($N.height) audio=$($N.audio_stream_present) captionOnlyAudio=$($C.audio_stream_present) restartAttempts=$($R.attempt_count)"

Write-Host "[30.5.9] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.9] PASS"
Write-Host "Proof: $Proof"
