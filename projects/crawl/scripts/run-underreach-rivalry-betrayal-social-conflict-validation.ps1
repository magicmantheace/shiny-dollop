$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-rivalry-betrayal-social-conflict-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30c5"
$Proof = Join-Path $Out "rivalry-betrayal-social-conflict-proof.json"
$Repro = Join-Path $Out "rivalry-betrayal-social-conflict-proof-repro.json"
$Seed = "underreach-30c5-rivalry-betrayal-proof"

Write-Host "[30C.5] Accepted 30A.1-30C.4 regressions + focused rivalry/betrayal/social-conflict tests"
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
  tests/test_underreach_30c5_rivalry_betrayal_social_conflict.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30C.5] Running deterministic rivalry/betrayal/social-conflict proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.rivalry-betrayal-social-conflict-proof.v1") { throw "30C.5 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.rivalry-betrayal-social-conflict.v1") { throw "30C.5 slice protocol changed" }
if ($P.digest -ne $Q.digest) { throw "30C.5 proof reproducibility digest mismatch" }
if ($P.descent_id -ne $Q.descent_id) { throw "30C.5 deterministic Descent identity mismatch" }
if ($P.final_snapshot_digest -ne $Q.final_snapshot_digest) { throw "30C.5 deterministic snapshot mismatch" }
if ($P.final_canonical_fingerprint -ne $Q.final_canonical_fingerprint) { throw "30C.5 canonical fingerprint mismatch" }
if ($P.authoritative -ne $true -or $P.canonical_owner -ne "deterministic_simulation") { throw "30C.5 authority boundary changed" }
if ($P.random_betrayal_allowed -ne $false -or $P.presentation_feedback_allowed -ne $false) { throw "30C.5 random/presentation boundary changed" }
if ([int]$P.population_count -ne 8 -or [int]$P.configured_stratum_count -ne 3) { throw "30C.5 proof population/Stratum shape changed" }
if ($P.neutral_betrayal_rejected -ne $true -or $P.neutral_rejection_side_effect_free -ne $true) { throw "30C.5 neutral betrayal safety changed" }
if ($P.neutral_betrayal_rejection_reason -notin @("insufficient_accumulated_conflict", "high_impact_negative_evidence_required")) { throw "30C.5 neutral betrayal rejection reason changed" }
if ($P.stale_rejection_reason -ne "stale_observation" -or $P.stale_rejection_side_effect_free -ne $true) { throw "30C.5 stale proposal rejection changed" }
if ([int]$P.evidence_observation_negative_memory_count -lt 2 -or [int]$P.evidence_observation_major_negative_memory_count -lt 1) { throw "30C.5 accumulated grievance evidence missing" }
if ([int]$P.evidence_observation_basis_event_count -lt 2) { throw "30C.5 grievance Ledger basis missing" }
if ($P.betrayal_executed -ne $true -or [int]$P.betrayal_basis_event_count -lt 2) { throw "30C.5 evidence-backed betrayal failed" }
if ($null -ne $P.betrayer_party_after) { throw "30C.5 betrayer remained in party" }
if ($P.betrayed_party_active -ne $true -or $P.betrayed_party_members_after.Count -ne 2) { throw "30C.5 betrayed party invariants changed" }
if ([double]$P.betrayed_target_resentment -le 0.0 -or [double]$P.betrayed_target_rivalry -le 0.0) { throw "30C.5 betrayal did not evolve rivalry/resentment" }
if ($P.alliance_break_executed -ne $true -or $P.hostile_alliance_archived -ne $true -or $P.hostile_alliance_removed_from_30c4 -ne $true) { throw "30C.5 hostile alliance break contract changed" }
if ($P.revenge_executed -ne $true -or [int]$P.active_revenge_count -ne 1 -or $P.revenge_started_combat -ne $false) { throw "30C.5 revenge state contract changed" }
if ($P.loot_theft_executed -ne $true -or $P.stolen_item_owner -ne "descender_007") { throw "30C.5 canonical loot theft failed" }
if ($P.deception_created -ne $true -or $P.deception_exposed -ne $true -or $P.deception_status -ne "exposed") { throw "30C.5 structured deception lifecycle changed" }
if ($P.aid_refusal_executed -ne $true) { throw "30C.5 aid refusal path failed" }
if ([int]$P.conflict_execution_count -ne 7) { throw "30C.5 deterministic conflict execution count changed" }
if ($P.independent_state_equal -ne $true -or $P.independent_snapshot_equal -ne $true -or $P.independent_event_ids_equal -ne $true) { throw "30C.5 independent deterministic reproduction failed" }
if ($P.checkpoint_state_equal -ne $true -or $P.checkpoint_snapshot_equal -ne $true) { throw "30C.5 checkpoint restore diverged" }
if ([int]$P.checkpoint_event_count -lt 1 -or -not $P.checkpoint_digest) { throw "30C.5 checkpoint proof incomplete" }

$E = $P.event_type_counts
if ([int]$E.SOCIAL_CONFLICT_SYSTEM_INITIALIZED -ne 1) { throw "30C.5 initialization event count changed" }
if ([int]$E.SOCIAL_CONFLICT_EXECUTED -ne 7) { throw "30C.5 execution Ledger count changed" }
if ([int]$E.BETRAYAL -lt 1) { throw "30C.5 betrayal Ledger event missing" }
if ([int]$E.ALLIANCE_BETRAYAL -ne 1) { throw "30C.5 alliance betrayal Ledger count changed" }
if ([int]$E.REVENGE_SEEKING_STARTED -ne 1) { throw "30C.5 revenge Ledger count changed" }
if ([int]$E.DECEPTION_CREATED -ne 1) { throw "30C.5 deception creation Ledger count changed" }
if ([int]$E.AID_REFUSED -ne 1) { throw "30C.5 aid refusal Ledger count changed" }
if ([int]$E.LOOT_STOLEN -lt 4) { throw "30C.5 loot-conflict/grievance Ledger coverage changed" }
if ([int]$E.PROMISE_VIOLATED -lt 4) { throw "30C.5 deception/grievance Ledger coverage changed" }

$A = $P.authority_contract
if ($A.conflict_proposal_is_advisory -ne $true -or $A.simulation_validates_conflict -ne $true -or $A.simulation_executes_conflict -ne $true) { throw "30C.5 proposal/execution authority changed" }
if ($A.random_betrayal_forbidden -ne $true -or $A.high_impact_conflict_requires_negative_evidence -ne $true -or $A.high_impact_conflict_requires_explicit_incentive -ne $true) { throw "30C.5 betrayal eligibility contract changed" }
if ($A.neutral_state_cannot_betray_from_incentive_alone -ne $true) { throw "30C.5 neutral-state betrayal guard changed" }
if ($A.loot_theft_uses_canonical_item_ownership -ne $true -or $A.party_betrayal_uses_30c4_membership_authority -ne $true) { throw "30C.5 item/party authority changed" }
if ($A.hostile_alliance_break_owned_by_30c5 -ne $true) { throw "30C.5 hostile alliance ownership changed" }
if ($A.deception_is_structured_not_prose -ne $true -or $A.deception_memory_only_after_exposure -ne $true) { throw "30C.5 deception authority changed" }
if ($A.revenge_state_does_not_start_combat -ne $true) { throw "30C.5 revenge/combat boundary changed" }
if ($A.presentation_can_mutate -ne $false -or $A.unreal_can_mutate -ne $false) { throw "30C.5 presentation authority changed" }
if ($A.dialogue_owner_phase -ne "31") { throw "30C.5 absorbed Phase 31 dialogue" }
if ($A.next_slice -notlike "30C.6*") { throw "30C.5 next canonical slice changed" }

Write-Host "[30C.5] Deterministic rivalry/betrayal/social-conflict proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) conflicts=$($P.conflict_execution_count) revenge=$($P.active_revenge_count)"
Write-Host "betrayalBasis=$($P.betrayal_basis_event_count) resentment=$($P.betrayed_target_resentment) rivalry=$($P.betrayed_target_rivalry)"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count)"
Write-Host "traceDigest=$($P.conflict_trace_digest)"

Write-Host "[30C.5] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30C.5] PASS"
Write-Host "Proof: $Proof"
