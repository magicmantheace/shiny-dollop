$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-narration-captions-audio-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_8"
$Proof = Join-Path $Out "narration-captions-audio-proof.json"
$Repro = Join-Path $Out "narration-captions-audio-proof-repro.json"
$Seed = "underreach-30-5-8-narration-captions-audio-proof"

Write-Host "[30.5.8] Accepted 30A.1-30.5.7 regressions + focused narration/caption/audio tests"
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
  tests/test_underreach_30_5_8_narration_captions_audio.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.8] Running deterministic file-backed narration/caption/audio proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.narration-captions-audio-proof.v1") { throw "30.5.8 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.narration-captions-audio.v1") { throw "30.5.8 slice protocol changed" }
if ($P.implementation_version -ne "30.5.8") { throw "30.5.8 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.8 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.8 audio snapshot reproducibility mismatch" }
if ($P.media.job_digest -ne $Q.media.job_digest) { throw "30.5.8 job reproducibility mismatch" }
if ($P.media.artifact_digest -ne $Q.media.artifact_digest) { throw "30.5.8 artifact reproducibility mismatch" }
if ($P.media.provider_execution_digest -ne $Q.media.provider_execution_digest) { throw "30.5.8 provider execution reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.8 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.8 presentation gained simulation authority" }
if ($A.unreal_dependency -ne $false) { throw "30.5.8 introduced Unreal dependency" }
if ($A.speech_recognition_used -ne $false) { throw "30.5.8 captions unexpectedly depend on speech recognition" }
if ($A.audio_mixing_performed -ne $false) { throw "30.5.8 stole FFmpeg mixing from 30.5.9" }
if ($A.caption_only_fallback_guaranteed -ne $true) { throw "30.5.8 lost caption-only fallback" }
if ($A.required_cloud_api -ne $false -or $A.required_paid_provider -ne $false) { throw "30.5.8 added required cloud/paid dependency" }
if ($P.canonical.unchanged_during_audio_production -ne $true) { throw "30.5.8 audio production changed canonical Crawl/Ledger truth" }

$V = $P.verified_input
if ($V.review_ready -ne $true) { throw "30.5.8 proof source was not REVIEW_READY" }
if ($V.script_verbatim -ne $true) { throw "30.5.8 narration script diverged from verified draft" }
if ($V.captions_match_sentences -ne $true -or [int]$V.caption_count -lt 1) { throw "30.5.8 captions no longer derive directly from verified script" }
if ($V.sound_assets_royalty_safe -ne $true -or $V.sound_assets_not_mixed -ne $true) { throw "30.5.8 sound metadata/mixing boundary changed" }

$N = $P.narrated
if ([int]$N.package_artifact_count -ne 4) { throw "30.5.8 narrated caption-package artifact count changed" }
if ([int]$N.voice_artifact_count -ne 2) { throw "30.5.8 narrated voice artifact count changed" }
if ($N.wav_exists -ne $true -or $N.wav_signature -ne $true) { throw "30.5.8 did not produce a real WAV file" }
if ($N.provider_local -ne $true) { throw "30.5.8 acceptance proof executed non-local voice provider" }
if ($N.caption_fallback_retained -ne $true) { throw "30.5.8 narrated package lost caption fallback" }

$D = $P.degraded
if ($D.package_completed -ne $true -or $D.caption_only_ready -ne $true) { throw "30.5.8 no-provider degradation did not produce caption-only package" }
if ([int]$D.caption_artifact_count -ne 4) { throw "30.5.8 degraded caption package artifact count changed" }
if ($D.voice_held -ne $true -or $D.voice_artifact_absent -ne $true) { throw "30.5.8 unavailable TTS did not remain safely held/degraded" }

$R = $P.restart
if ([int]$R.recovered_count -ne 1 -or $R.same_voice_job -ne $true) { throw "30.5.8 restart did not recover same voice job" }
if ([int]$R.attempt_count -ne 2 -or $R.completed -ne $true) { throw "30.5.8 restart voice retry/complete contract changed" }

$I = $P.idempotency
if ($I.repeat_package_same_job -ne $true -or $I.repeat_voice_same_job -ne $true) { throw "30.5.8 repeat enqueue changed durable job identity" }
if ($I.snapshot_equal_after_repeat -ne $true) { throw "30.5.8 completed re-enqueue duplicated media state" }

$G = $P.routing
if ($G.paid_blocked_by_default -ne $true) { throw "30.5.8 paid voice provider was not blocked by default" }
if ($G.paid_selected_with_all_gates -ne $true) { throw "30.5.8 explicit paid voice routing probe failed" }

$M = $P.media
if ([int]$M.job_count -ne 4) { throw "30.5.8 audio job count changed" }
if ([int]$M.artifact_count -ne 10) { throw "30.5.8 audio artifact count changed" }
if ([int]$M.provider_execution_count -ne 1) { throw "30.5.8 provider execution count changed" }

Write-Host "[30.5.8] Narration, captions & audio proof PASS"
Write-Host "digest=$($P.digest) jobs=$($M.job_count) artifacts=$($M.artifact_count) executions=$($M.provider_execution_count)"
Write-Host "restartAttempts=$($R.attempt_count) captionOnly=$($D.caption_only_ready) canonicalUnchanged=$($P.canonical.unchanged_during_audio_production)"

Write-Host "[30.5.8] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.8] PASS"
Write-Host "Proof: $Proof"
