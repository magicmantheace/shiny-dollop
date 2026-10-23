$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-unattended-promotion-soak-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_12"
$Proof = Join-Path $Out "unattended-promotion-soak-proof.json"
$Repro = Join-Path $Out "unattended-promotion-soak-proof-repro.json"
$Seed = "underreach-30-5-12-unattended-promotion-soak-proof"

Write-Host "[30.5.12] Accepted 30A.1-30.5.11 regression gate"
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
  tests/test_underreach_30_5_10_local_video_enhancement_gpu_scheduling.py `
  tests/test_underreach_30_5_11_media_website_blog_generation.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.12] Verifying required local FFmpeg capabilities"
$FfmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$FfprobeCommand = Get-Command ffprobe -ErrorAction SilentlyContinue
if ($null -eq $FfmpegCommand) { throw "30.5.12 requires local ffmpeg on PATH" }
if ($null -eq $FfprobeCommand) { throw "30.5.12 requires local ffprobe on PATH" }
$EncoderText = (& ffmpeg -hide_banner -encoders 2>&1 | Out-String)
if ($EncoderText -notmatch "libx264") { throw "30.5.12 requires FFmpeg libx264" }
$FilterText = (& ffmpeg -hide_banner -filters 2>&1 | Out-String)
foreach ($Filter in @("subtitles", "xfade", "zoompan", "loudnorm", "afade")) {
    if ($FilterText -notmatch $Filter) { throw "30.5.12 FFmpeg build lacks required filter: $Filter" }
}

Write-Host "[30.5.12] Source boundary audit"
$Source = Get-Content -Raw (Join-Path $RepoRoot "src\livingworld\underreach_unattended_promotion_soak.py")
if ($Source -match "UnrealEditor" -or $Source -match "unreal\." -or $Source -match "import\s+unreal") {
    throw "30.5.12 introduced an Unreal dependency"
}
if ($Source -match "import\s+requests" -or $Source -match "import\s+httpx" -or $Source -match "from\s+openai" -or $Source -match "from\s+anthropic") {
    throw "30.5.12 introduced a required network/cloud client"
}
if ($Source -notmatch 'population_count: int = Field\(default=20, ge=20' -or $Source -notmatch 'required_social_events: int = Field\(default=4, ge=4') {
    throw "30.5.12 meaningful-soak population/social acceptance floor changed"
}
if ($Source -notmatch '"recruit"' -or $Source -notmatch '"accept_recruitment"' -or $Source -notmatch 'form_from_accepted_recruitment') {
    throw "30.5.12 lost accepted 30C.3/30C.4 recruitment-party social chain"
}
if ($Source -notmatch '"PROMISE_VIOLATED"' -or $Source -notmatch '"betray_party"' -or $Source -notmatch 'incentive_code="revenge"') {
    throw "30.5.12 lost reinforced-memory/evidence-backed 30C.5 betrayal proof"
}
if ($Source -notmatch 'score\.danger < 10' -or $Source -notmatch 'score\.social_stakes < 20' -or $Source -notmatch 'score\.continuity < 15' -or $Source -notmatch 'score\.visual_potential < 5') {
    throw "30.5.12 lost deterministic 50-point highlight component floor"
}
if ($Source -notmatch 'REVIEW_JOB_TYPE = "underreach\.review-queue\.build"' -or $Source -notmatch 'automatic_publication_allowed') {
    throw "30.5.12 lost durable pending-human-review queue contract"
}
if ($Source -notmatch "canonical_database_url" -or $Source -notmatch "media_database_url") {
    throw "30.5.12 lost physically separate canonical/media store contract"
}
if ($Source -notmatch "DeterministicLocalPngProvider" -or $Source -notmatch "DeterministicLocalWavProvider" -or $Source -notmatch "AutomatedFfmpegMotionStoryService") {
    throw "30.5.12 lost guaranteed local image/audio/FFmpeg production path"
}

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.12] Running full unattended promotion soak proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.unattended-promotion-soak-proof.v1") { throw "30.5.12 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.unattended-promotion-soak.v1") { throw "30.5.12 slice protocol changed" }
if ($P.implementation_version -ne "30.5.12") { throw "30.5.12 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.12 soak reproducibility digest mismatch" }
if ($P.canonical.final_state_digest -ne $Q.canonical.final_state_digest) { throw "30.5.12 canonical final-state reproducibility mismatch" }
if ($P.canonical.final_ledger_digest -ne $Q.canonical.final_ledger_digest) { throw "30.5.12 canonical Ledger reproducibility mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.12 media snapshot reproducibility mismatch" }
if ($P.promotion.output_digest -ne $Q.promotion.output_digest) { throw "30.5.12 promo MP4 reproducibility mismatch" }
if ($P.review_queue.review_manifest_digest -ne $Q.review_queue.review_manifest_digest) { throw "30.5.12 review queue reproducibility mismatch" }
if ($P.website.build_id -ne $Q.website.build_id) { throw "30.5.12 static website build identity mismatch" }

$C = $P.canonical
if ([int]$C.population_count -lt 20) { throw "30.5.12 unattended population dropped below 20" }
if ($C.outcome -ne "completed") { throw "30.5.12 canonical crawl did not complete" }
if ([int]$C.encounters_resolved -le 0) { throw "30.5.12 canonical crawl produced no encounter resolution" }
if ([int]$C.strata_advanced -lt 2 -or [int]$C.final_stratum -ne 3) { throw "30.5.12 canonical multi-Stratum progression changed" }
if ($C.bootstrap_export_unchanged -ne $true -or $C.unchanged_during_downstream_media -ne $true) {
    throw "30.5.12 media pipeline mutated canonical simulation truth"
}

$E = $P.event_provenance
if ($null -eq $E.combat_event_ids -or $E.combat_event_ids.Count -lt 1) { throw "30.5.12 lacks real combat provenance" }
if ($null -eq $E.progression_event_ids -or $E.progression_event_ids.Count -lt 1) { throw "30.5.12 lacks real progression provenance" }
if ($null -eq $E.social_pair_ids -or $E.social_pair_ids.Count -ne 2 -or [string]::IsNullOrWhiteSpace([string]$E.social_party_id) -or [string]::IsNullOrWhiteSpace([string]$E.recruitment_offer_id)) {
    throw "30.5.12 canonical recruitment/party social proof is incomplete"
}
$PromiseIds = @($E.promise_violation_event_ids)
$SocialIds = @($E.social_event_ids)
$CompositeIds = @($E.composite_source_event_ids)
if ($PromiseIds.Count -lt 4 -or [string]::IsNullOrWhiteSpace([string]$E.betrayal_event_id)) {
    throw "30.5.12 lacks reinforced promises plus evidence-backed betrayal"
}
if ([double]$E.betrayal_conflict_score -lt 0.58) { throw "30.5.12 betrayal conflict score fell below accepted 30C.5 threshold" }
if ($SocialIds.Count -lt 5) { throw "30.5.12 social provenance lost the promise/betrayal chain" }
foreach ($PromiseId in $PromiseIds) {
    if ($CompositeIds -notcontains $PromiseId) { throw "30.5.12 featured composite lost a canonical promise-violation event" }
}
if ($CompositeIds -notcontains $E.betrayal_event_id) { throw "30.5.12 featured composite lost the canonical betrayal event" }
if ($CompositeIds.Count -lt 7) { throw "30.5.12 composite promotion envelope is under-provenanced" }
$Score = $E.composite_highlight_components
if ($null -eq $Score) { throw "30.5.12 proof lost highlight score components" }
if ([int]$E.composite_highlight_floor -ne 50) { throw "30.5.12 deterministic highlight floor changed" }
if ([int]$Score.danger -lt 10 -or [int]$Score.social_stakes -lt 20 -or [int]$Score.continuity -lt 15 -or [int]$Score.visual_potential -lt 5) {
    throw "30.5.12 canonical combat/betrayal/memory/visual highlight floor changed"
}
if ([int]$Score.total -lt 50 -or [int]$E.composite_highlight_score -ne [int]$Score.total) {
    throw "30.5.12 real composite envelope did not clear its guaranteed highlight threshold"
}
if ($null -ne $E.composite_foreign_actor_ids -and $E.composite_foreign_actor_ids.Count -ne 0) { throw "30.5.12 composite envelope contains non-Delver actors" }
$EncounterRetreatIds = @($E.encounter_retreat_event_ids)
$TerminalMediaIds = @($E.terminal_media_event_ids)
foreach ($RetreatId in $EncounterRetreatIds) {
    if ($TerminalMediaIds -contains $RetreatId) { throw "30.5.12 encounter retreat leaked into terminal Chronicle export" }
}

$M = $P.media
if ([int]$M.profile_count -lt 20) { throw "30.5.12 media Delver directory lost the 20+ roster" }
if ([int]$M.envelope_count -lt 7) { throw "30.5.12 media export count is unexpectedly small" }
if ([int]$M.job_count -lt 7 -or [int]$M.artifact_count -lt 10) { throw "30.5.12 durable media pipeline did not materialize expected work" }
if ([int]$M.paid_execution_count -ne 0) { throw "30.5.12 executed paid media work with paid providers disabled" }
if ($null -ne $M.nonlocal_provider_ids -and $M.nonlocal_provider_ids.Count -ne 0) { throw "30.5.12 acceptance path invoked a non-local media provider" }

$H = $P.chronicle
if ([int]$H.chapter_count -lt 1 -or [int]$H.highlight_count -lt 1) { throw "30.5.12 Chronicle/highlight production failed" }
if ($null -eq $H.source_event_ids -or $H.source_event_ids.Count -lt 1) { throw "30.5.12 featured Chronicle lost Ledger provenance" }

$V = $P.verification
if ($V.status -ne "review_ready" -or $V.review_ready -ne $true) { throw "30.5.12 narrative did not become REVIEW_READY" }
if ([int]$V.deterministic_contradiction_count -ne 0 -or [int]$V.unsupported_claim_count -ne 0) { throw "30.5.12 verified narrative contains rejected claims" }
if ($V.writer_provider_local -ne $true -or $V.writer_provider_paid -ne $false) { throw "30.5.12 acceptance writer boundary changed" }

$R = $P.restart
if ([int]$R.recovered_job_count -ne 1 -or $R.same_scene_job -ne $true -or [int]$R.scene_attempt_count -ne 2) {
    throw "30.5.12 injected media-worker restart did not recover same scene job on attempt 2"
}
$I = $P.idempotency
if ($I.envelope_reregistration_stable -ne $true -or $I.scene_completed_reenqueue_reused_job -ne $true -or $I.review_queue_completed_reenqueue_reused_job -ne $true) {
    throw "30.5.12 restart/idempotency contract changed"
}

$A = $P.audio
if ($A.package_status -ne "completed" -or $A.caption_only_ready -ne $true -or $A.voice_status -ne "completed") {
    throw "30.5.12 local narration/caption package did not complete"
}
if ($A.voice_provider_id -ne "local_deterministic_wav") { throw "30.5.12 acceptance voice provider changed" }

$X = $P.promotion
if ($X.status -ne "completed") { throw "30.5.12 FFmpeg motion story did not complete" }
if ([int]$X.width * 16 -ne [int]$X.height * 9) { throw "30.5.12 final promotion is not exact 9:16" }
if ($X.motion_story_fallback_guaranteed -ne $true -or $X.video_diffusion_required -ne $false -or $X.ffmpeg_local -ne $true) {
    throw "30.5.12 guaranteed local motion-story path changed"
}
if ($X.audio_stream_present -ne $true) { throw "30.5.12 finished promotion lost local narration audio" }

$QItem = $P.review_queue
if ($QItem.review_status -ne "pending" -or $QItem.published -ne $false -or $QItem.review_ready -ne $true) {
    throw "30.5.12 final promotion did not stop in pending review state"
}
if ($QItem.human_intervention_required_before_review -ne $false -or $QItem.human_review_required_before_publication -ne $true) {
    throw "30.5.12 human-review boundary changed"
}

$W = $P.website
if ($W.status -ne "completed" -or $W.static_only -ne $true -or $W.live_database_required_after_build -ne $false) {
    throw "30.5.12 static website did not complete independently"
}
if ([int]$W.profile_count -lt 20 -or [int]$W.verified_narrative_count -lt 1 -or [int]$W.highlight_count -lt 1) {
    throw "30.5.12 website content acceptance counts failed"
}
if ([int]$W.published_video_count -ne 0) { throw "30.5.12 pending review video leaked into public website" }

foreach ($Property in $P.mandatory_zeroes.PSObject.Properties) {
    if ($Property.Value -ne $true) { throw "30.5.12 mandatory zero failed: $($Property.Name)" }
}
$Authority = $P.authority_contract
if ($Authority.canonical_owner -ne "deterministic_simulation" -or $Authority.presentation_can_mutate_simulation -ne $false) {
    throw "30.5.12 authority boundary changed"
}
if ($Authority.media_database_is_separate -ne $true -or $Authority.review_queue_can_publish_automatically -ne $false) {
    throw "30.5.12 media-store/review boundary changed"
}
if ($Authority.optional_video_enhancement_required_for_acceptance -ne $false) { throw "30.5.12 made video diffusion a hard dependency" }

$ProofRuntime = Join-Path $Out "unattended-promotion-soak-proof-runtime\media"
$PromoPath = Join-Path $ProofRuntime ($X.output_uri -replace '/', '\')
$ReviewPath = Join-Path $ProofRuntime ($QItem.review_manifest_uri -replace '/', '\')
$WebsiteIndex = Join-Path $ProofRuntime (($W.public_root -replace '/', '\') + "\index.html")
if (-not (Test-Path $PromoPath)) { throw "30.5.12 proof MP4 is missing from disk" }
if (-not (Test-Path $ReviewPath)) { throw "30.5.12 review queue manifest is missing from disk" }
if (-not (Test-Path $WebsiteIndex)) { throw "30.5.12 static website index is missing from disk" }

Write-Host "[30.5.12] Unattended promotion soak proof PASS"
Write-Host "digest=$($P.digest) population=$($C.population_count) events=$($C.final_event_count) profiles=$($M.profile_count) highlight=$($E.composite_highlight_score)"
Write-Host "promo=$($X.output_uri) review=$($QItem.review_status) website=$($W.status) restartAttempts=$($R.scene_attempt_count)"

Write-Host "[30.5.12] Full repository regression suite (includes focused capstone tests)"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.12] PASS"
Write-Host "Proof: $Proof"