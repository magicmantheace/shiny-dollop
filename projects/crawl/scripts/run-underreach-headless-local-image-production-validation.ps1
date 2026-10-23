$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-headless-local-image-production-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_7"
$Proof = Join-Path $Out "headless-local-image-production-proof.json"
$Repro = Join-Path $Out "headless-local-image-production-proof-repro.json"
$Seed = "underreach-30-5-7-headless-local-image-production-proof"

Write-Host "[30.5.7] Accepted 30A.1-30.5.6 regressions + focused headless image-production tests"
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
  tests/test_underreach_30_5_7_headless_local_image_production.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.7] Running deterministic file-backed headless image-production proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.headless-local-image-production-proof.v1") { throw "30.5.7 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.headless-image-production.v1") { throw "30.5.7 slice protocol changed" }
if ($P.implementation_version -ne "30.5.7") { throw "30.5.7 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.7 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.7 snapshot reproducibility mismatch" }
if ($P.media.job_digest -ne $Q.media.job_digest) { throw "30.5.7 job reproducibility mismatch" }
if ($P.media.artifact_digest -ne $Q.media.artifact_digest) { throw "30.5.7 artifact reproducibility mismatch" }
if ($P.media.provider_execution_digest -ne $Q.media.provider_execution_digest) { throw "30.5.7 provider execution reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.7 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.7 presentation gained simulation authority" }
if ($A.unreal_dependency -ne $false) { throw "30.5.7 introduced Unreal dependency" }
if ($A.required_cloud_api -ne $false -or $A.required_paid_provider -ne $false) { throw "30.5.7 added required cloud/paid dependency" }
if ($P.canonical.unchanged_during_image_production -ne $true) { throw "30.5.7 image production changed canonical Crawl/Ledger truth" }

$I = $P.identity
if ([int]$I.identity_version -ne 1) { throw "30.5.7 unexpected identity version" }
if ($I.portrait_static_not_equipment_coupled -ne $true) { throw "30.5.7 static portrait became equipment-coupled" }
if ($I.equipment_spec_has_revision -ne $true) { throw "30.5.7 equipment image lost equipment revision provenance" }

$X = $P.production
if ([int]$X.job_count -ne 4) { throw "30.5.7 image job count changed" }
if ([int]$X.artifact_count -ne 8) { throw "30.5.7 artifact count changed" }
if ([int]$X.provider_execution_count -ne 4) { throw "30.5.7 provider execution count changed" }
if ([int]$X.image_artifact_count -ne 4 -or [int]$X.sidecar_artifact_count -ne 4) { throw "30.5.7 PNG/sidecar artifact contract changed" }
if ($X.all_image_files_exist -ne $true -or $X.all_image_files_are_png -ne $true) { throw "30.5.7 did not produce real PNG files" }
if ($X.repeat_portrait_reused_job -ne $true -or $X.snapshot_equal_after_completed_reenqueue -ne $true) { throw "30.5.7 completed image re-enqueue duplicated work" }
if ($X.scene_uses_reference_artifact -ne $true -or $X.scene_has_chapter_provenance -ne $true) { throw "30.5.7 scene still lost reference/chapter provenance" }
if ($X.local_provider_only -ne $true) { throw "30.5.7 acceptance proof executed a non-local image provider" }

$R = $P.restart
if ([int]$R.recovered_count -ne 1 -or $R.same_job_id -ne $true) { throw "30.5.7 restart did not recover the same durable job" }
if ([int]$R.attempt_count -ne 2 -or $R.completed -ne $true) { throw "30.5.7 restart retry/complete contract changed" }

$G = $P.routing
if ($G.local_under_12gb_provider -ne "proof_local_11gb") { throw "30.5.7 local 12GB routing choice changed" }
if ($G.oversized_16gb_excluded -ne $true) { throw "30.5.7 16GB provider escaped 12GB resource bound" }
if ($G.paid_blocked_without_global_permission -ne $true) { throw "30.5.7 paid provider was not blocked by default" }
if ($G.paid_selected_with_all_gates -ne $true) { throw "30.5.7 explicit paid-provider gate probe failed" }

Write-Host "[30.5.7] Headless local image-production proof PASS"
Write-Host "digest=$($P.digest) jobs=$($X.job_count) images=$($X.image_artifact_count) executions=$($X.provider_execution_count)"
Write-Host "restartAttempts=$($R.attempt_count) provider=$($G.local_under_12gb_provider) canonicalUnchanged=$($P.canonical.unchanged_during_image_production)"

Write-Host "[30.5.7] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.7] PASS"
Write-Host "Proof: $Proof"
