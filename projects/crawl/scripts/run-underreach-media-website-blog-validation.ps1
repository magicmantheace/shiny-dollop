$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-media-website-blog-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_11"
$Proof = Join-Path $Out "media-website-blog-proof.json"
$Repro = Join-Path $Out "media-website-blog-proof-repro.json"
$Seed = "underreach-30-5-11-media-website-blog-proof"

Write-Host "[30.5.11] Accepted 30A.1-30.5.10 regressions + focused static website/blog tests"
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

Write-Host "[30.5.11] Verifying static media-only source boundary"
$SourcePath = Join-Path $RepoRoot "src\livingworld\underreach_media_website_blog.py"
$Source = Get-Content -Raw $SourcePath
if ($Source -match "from\s+\.crawl_" -or $Source -match "import\s+livingworld\.crawl_" -or $Source -match "CrawlPersistence" -or $Source -match "BrainDrivenDescentService") {
    throw "30.5.11 production module imported canonical simulation/database services"
}
if ($Source -match "import\s+requests" -or $Source -match "import\s+httpx" -or $Source -match "from\s+openai" -or $Source -match "import\s+subprocess") {
    throw "30.5.11 production module introduced network/provider/process dependency"
}
if ($Source -notmatch "VerificationStatus\.REVIEW_READY") {
    throw "30.5.11 lost verification-cleared prose publication gate"
}
if ($Source -notmatch 'review_status.*approved' -or $Source -notmatch 'published') {
    throw "30.5.11 lost approved/published promotional-media gate"
}
if ($Source -notmatch "live_database_required_after_build.*False" -or $Source -notmatch "static_only.*True") {
    throw "30.5.11 lost static-site/no-live-database contract"
}

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.11] Running deterministic file-backed static website proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.media-website-blog-proof.v1") { throw "30.5.11 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.media-website-blog.v1") { throw "30.5.11 slice protocol changed" }
if ($P.implementation_version -ne "30.5.11") { throw "30.5.11 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.11 proof reproducibility digest mismatch" }
if ($P.public_input.source_digest -ne $Q.public_input.source_digest) { throw "30.5.11 public-source reproducibility mismatch" }
if ($P.build.manifest_digest -ne $Q.build.manifest_digest) { throw "30.5.11 manifest reproducibility mismatch" }
if ($P.build.static_file_digest -ne $Q.build.static_file_digest) { throw "30.5.11 static-file reproducibility mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.11 media snapshot reproducibility mismatch" }
if ($P.media.job_digest -ne $Q.media.job_digest) { throw "30.5.11 website-job reproducibility mismatch" }
if ($P.media.artifact_digest -ne $Q.media.artifact_digest) { throw "30.5.11 website-artifact reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.11 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.11 presentation gained simulation authority" }
if ($A.canonical_database_opened -ne $false -or $A.live_simulation_query_used -ne $false) { throw "30.5.11 accessed canonical/live simulation paths" }
if ($A.provider_invocation_used -ne $false -or $A.network_dependency -ne $false -or $A.unreal_dependency -ne $false) { throw "30.5.11 introduced provider/network/Unreal dependency" }
if ($A.live_database_required_after_build -ne $false -or $A.static_only -ne $true) { throw "30.5.11 output is no longer a standalone static site" }

$I = $P.public_input
if ([int]$I.profile_count -ne 3 -or [int]$I.chapter_count -ne 3) { throw "30.5.11 profile/Chronicle fixture counts changed" }
if ([int]$I.verified_narrative_count -ne 1 -or [int]$I.excluded_unverified_draft_count -ne 1) { throw "30.5.11 verification publication boundary changed" }
if ([int]$I.highlight_count -ne 1 -or [int]$I.portrait_count -ne 1 -or [int]$I.published_video_count -ne 1) { throw "30.5.11 public media selection counts changed" }
if ([int]$I.source_artifact_count -ne 2) { throw "30.5.11 public source artifact count changed" }

$C = $P.content_guards
if ($C.review_ready_text_present -ne $true) { throw "30.5.11 review-ready prose was not published" }
if ($C.rejected_text_absent -ne $true) { throw "30.5.11 rejected prose leaked into public HTML" }
if ($C.pending_story_absent -ne $true -or $C.pending_video_bytes_absent -ne $true) { throw "30.5.11 pending promotional media leaked into public site" }
if ($C.approved_story_present -ne $true) { throw "30.5.11 approved published reel missing from site" }
if ($C.active_status_page -ne $true -or $C.retreated_status_page -ne $true -or $C.dead_status_page -ne $true) { throw "30.5.11 Delver status filters/pages are incomplete" }
if ([int]$C.copied_portrait_count -ne 1 -or [int]$C.copied_video_count -ne 1) { throw "30.5.11 portable media-copy counts changed" }

$B = $P.build
if ([int]$B.page_count -ne 13) { throw "30.5.11 HTML page count changed" }
if ([int]$B.copied_asset_count -ne 2) { throw "30.5.11 copied public asset count changed" }
if ([int]$B.artifact_count -ne 17) { throw "30.5.11 recorded website artifact count changed" }
if ([int]$B.static_file_count -ne 17) { throw "30.5.11 static file-tree count changed" }
if ($B.static_survives_database_close -ne $true) { throw "30.5.11 generated site still depends on live SQLite after build" }
if ($B.manifest_source_digest -ne $I.source_digest) { throw "30.5.11 site manifest lost public-source identity" }

$R = $P.restart
if ([int]$R.recovered_count -ne 1 -or $R.same_job -ne $true) { throw "30.5.11 restart did not recover same website job" }
if ([int]$R.attempt_count -ne 2 -or $R.completed -ne $true) { throw "30.5.11 recovered website job did not complete on attempt 2" }

$D = $P.idempotency
if ($D.repeat_spec_same_build -ne $true -or $D.repeat_same_job -ne $true -or $D.snapshot_equal_after_repeat -ne $true) { throw "30.5.11 completed rebuild request was not idempotent" }

$M = $P.media
if ([int]$M.job_count -ne 1) { throw "30.5.11 website job count changed" }
if ([int]$M.artifact_count -ne 17) { throw "30.5.11 website media artifact count changed" }

Write-Host "[30.5.11] Media website / blog generation proof PASS"
Write-Host "digest=$($P.digest) pages=$($B.page_count) assets=$($B.copied_asset_count) artifacts=$($B.artifact_count)"
Write-Host "restartAttempts=$($R.attempt_count) verified=$($I.verified_narrative_count) rejectedLeak=$(-not $C.rejected_text_absent) static=$($A.static_only)"

Write-Host "[30.5.11] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.11] PASS"
Write-Host "Proof: $Proof"
