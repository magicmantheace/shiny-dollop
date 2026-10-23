$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-presentation-identity-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_6"
$Proof = Join-Path $Out "presentation-identity-proof.json"
$Repro = Join-Path $Out "presentation-identity-proof-repro.json"
$Seed = "underreach-30-5-6-presentation-identity-proof"

Write-Host "[30.5.6] Accepted 30A.1-30.5.5 regressions + focused presentation identity tests"
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
  tests/test_underreach_30_5_6_presentation_identity_system.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.6] Running deterministic file-backed presentation identity proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.presentation-identity-proof.v1") { throw "30.5.6 proof protocol changed" }
if ($P.slice_protocol -ne "presentation_identity.v1") { throw "30.5.6 slice protocol changed" }
if ($P.implementation_version -ne "30.5.6") { throw "30.5.6 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.6 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.6 snapshot reproducibility mismatch" }
if ($P.media.identity_digest -ne $Q.media.identity_digest) { throw "30.5.6 identity reproducibility mismatch" }
if ($P.media.equipment_revision_digest -ne $Q.media.equipment_revision_digest) { throw "30.5.6 equipment revision reproducibility mismatch" }
if ($P.media.binding_digest -ne $Q.media.binding_digest) { throw "30.5.6 binding reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.6 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.6 presentation gained simulation authority" }
if ($A.canonical_identity_fields_added -ne $false) { throw "30.5.6 generated presentation data became canonical identity" }
if ($A.generated_visuals_used -ne $false) { throw "30.5.6 generated visual artifacts before image-production slice" }
if ($A.provider_invocation_used -ne $false -or $A.generation_jobs_created -ne $false) { throw "30.5.6 invoked/scheduled image generation" }
if ($A.unreal_dependency -ne $false) { throw "30.5.6 introduced Unreal dependency" }
if ($A.cloud_api_required -ne $false -or $A.paid_provider_required -ne $false) { throw "30.5.6 added required cloud/paid dependency" }

$C = $P.canonical
if ($C.first_identity_step_unchanged -ne $true) { throw "30.5.6 first identity allocation changed canonical state" }
if ($C.equipment_sync_step_unchanged -ne $true) { throw "30.5.6 equipment sync changed canonical state" }
if ($C.version_switch_step_unchanged -ne $true) { throw "30.5.6 renderer version switch changed canonical state" }

$I = $P.identity
if ([int]$I.first_version -ne 1 -or [int]$I.second_version -ne 1) { throw "30.5.6 base identity version changed" }
if ($I.second_same_identity -ne $true) { throw "30.5.6 equipment update incorrectly changed face/body identity" }
if ([int]$I.renderer_switch_version -ne 2) { throw "30.5.6 renderer profile switch did not create identity v2" }
if ($I.renderer_switch_identity_id -eq $I.first_identity_id) { throw "30.5.6 renderer switch reused old identity ID" }
if ([int64]$I.renderer_switch_seed -eq [int64]$I.first_seed) { throw "30.5.6 renderer switch did not change deterministic presentation seed" }
if ([int]$I.identity_count -ne 2 -or [int]$I.identity_version_count -ne 2) { throw "30.5.6 identity version count changed" }
if ($I.active_identity_id -ne $I.renderer_switch_identity_id) { throw "30.5.6 active binding does not point to newest identity" }
$slotCounts = @($I.static_slot_count_per_identity)
if ($slotCounts.Count -ne 2 -or ($slotCounts | Where-Object { [int]$_ -ne 6 }).Count -ne 0) { throw "30.5.6 static reference slot contract changed" }
if ($I.all_static_slots_pending -ne $true) { throw "30.5.6 static reference slot was prematurely generated" }
if ($I.all_traits_empty -ne $true) { throw "30.5.6 invented facial/body presentation traits" }

$E = $P.equipment
if ($E.changed_revision -ne $true) { throw "30.5.6 visible equipment change did not create new equipment revision" }
if ($E.identity_unchanged_on_equipment_change -ne $true) { throw "30.5.6 equipment change incorrectly created new identity" }
if ([int]$E.first_identity_revision_count -ne 2) { throw "30.5.6 equipment revision count changed" }
if ($E.first_revision_has_relic -ne $true) { throw "30.5.6 initial equipment reference lost canonical Relic" }
if ($E.second_revision_empty -ne $true) { throw "30.5.6 dropped Relic remained in current equipment reference" }
if ($E.second_revision_uses_latest_ledger_prefix -ne $true) { throw "30.5.6 equipment revision did not follow canonical Ledger-prefix ordering" }
if ($E.all_equipment_slots_pending -ne $true) { throw "30.5.6 equipment reference was prematurely generated" }

$M = $P.media
if ($M.snapshot_equal_after_repeat -ne $true -or $M.repeat_state_equal -ne $true) { throw "30.5.6 repeat sync was not idempotent" }
if ($M.snapshot_equal_after_reopen -ne $true) { throw "30.5.6 media snapshot changed after SQLite reopen" }
if ($M.snapshot_equal_after_reopen_repeat -ne $true -or $M.reopen_repeat_state_equal -ne $true) { throw "30.5.6 restart repeat sync changed identity state" }
if ([int]$M.media_job_count -ne 0) { throw "30.5.6 unexpectedly enqueued generation jobs" }
if ([int]$M.provider_execution_count -ne 0) { throw "30.5.6 unexpectedly recorded provider execution" }

Write-Host "[30.5.6] Presentation identity proof PASS"
Write-Host "digest=$($P.digest) identities=$($I.identity_count) activeVersion=$($I.renderer_switch_version) equipmentRevisions=$($E.first_identity_revision_count)"
Write-Host "staticPending=$($I.all_static_slots_pending) equipmentPending=$($E.all_equipment_slots_pending) jobs=$($M.media_job_count)"

Write-Host "[30.5.6] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.6] PASS"
Write-Host "Proof: $Proof"
