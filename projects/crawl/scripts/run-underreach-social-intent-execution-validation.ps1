$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-social-intent-execution-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30c3"
$Proof = Join-Path $Out "social-intent-execution-proof.json"
$Repro = Join-Path $Out "social-intent-execution-proof-repro.json"
$Seed = "underreach-30c3-social-intent-proof"

Write-Host "[30C.3] Accepted 30A.1-30C.2 regressions + focused social-intent tests"
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
  tests/test_underreach_30c3_social_intent_interaction_execution.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30C.3] Running deterministic social-intent proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 6 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 6 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.social-intent-execution-proof.v1") {
  throw "30C.3 proof protocol changed"
}
if ($P.slice_protocol -ne "underreach.social-intent-execution.v1") {
  throw "30C.3 slice protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30C.3 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30C.3 deterministic Descent identity mismatch"
}
if ($P.final_snapshot_digest -ne $Q.final_snapshot_digest) {
  throw "30C.3 deterministic social-intent snapshot mismatch"
}
if ($P.final_canonical_fingerprint -ne $Q.final_canonical_fingerprint) {
  throw "30C.3 deterministic canonical fingerprint mismatch"
}
if ($P.authoritative -ne $true -or $P.canonical_owner -ne "deterministic_simulation") {
  throw "30C.3 canonical authority boundary changed"
}
if ($P.provider_can_mutate -ne $false -or $P.proposal_can_mutate -ne $false) {
  throw "30C.3 proposal/provider mutation boundary changed"
}
if ($P.presentation_feedback_allowed -ne $false -or $P.party_mutation_enabled -ne $false) {
  throw "30C.3 presentation/party scope boundary changed"
}
if ([int]$P.population_count -ne 6 -or [int]$P.configured_stratum_count -ne 3) {
  throw "30C.3 acceptance population/Stratum shape changed"
}
if ($P.proposal_side_effect_free -ne $true) {
  throw "30C.3 social proposal mutated canonical state"
}
if ($P.stale_rejection_side_effect_free -ne $true -or $P.stale_rejection_reason -ne "stale_observation") {
  throw "30C.3 stale proposal rejection contract changed"
}
if ([int]$P.execution_count -ne 8) {
  throw "30C.3 deterministic interaction execution count changed"
}
if ([int]$P.recruitment_offer_count -ne 2) {
  throw "30C.3 recruitment offer count changed"
}
if ([int]$P.accepted_recruitment_count -ne 1 -or [int]$P.refused_recruitment_count -ne 1) {
  throw "30C.3 recruitment resolution coverage changed"
}
if ([int]$P.party_count -ne 0 -or [int]$P.participants_with_party -ne 0) {
  throw "30C.3 illegally created persistent party state"
}
if ($P.shared_item_owner -ne "descender_001") {
  throw "30C.3 ordinary item sharing did not transfer canonical ownership"
}
if ($P.shared_supply_owner -ne "descender_001") {
  throw "30C.3 survival-supply sharing did not transfer canonical ownership"
}
if ([int]$P.shared_memory_reinforcement_count -ne 2 -or [int]$P.shared_memory_source_event_count -ne 2) {
  throw "30C.3 sharing did not feed/reinforce accepted 30C.2 memory"
}
if ([double]$P.receiver_trust -le 0.0 -or [double]$P.receiver_gratitude -le 0.0) {
  throw "30C.3 sharing did not evolve accepted relationship state"
}
if (-not $P.warning_sector_id -or [double]$P.warning_knowledge_confidence -le 0.0 -or [double]$P.warning_knowledge_confidence -gt 0.95) {
  throw "30C.3 warning knowledge transfer is invalid"
}
if ($P.independent_state_equal -ne $true -or $P.independent_snapshot_equal -ne $true -or $P.independent_event_ids_equal -ne $true) {
  throw "30C.3 independent deterministic reproduction failed"
}
if ($P.checkpoint_state_equal -ne $true -or $P.checkpoint_snapshot_equal -ne $true) {
  throw "30C.3 checkpoint-restored interaction state diverged"
}
if ([int]$P.checkpoint_event_count -lt 1 -or -not $P.checkpoint_digest) {
  throw "30C.3 checkpoint proof is incomplete"
}

$E = $P.event_type_counts
if ([int]$E.SOCIAL_INTENT_EXECUTION_INITIALIZED -ne 1) { throw "30C.3 initialization event count changed" }
if ([int]$E.SOCIAL_INTENT_EXECUTED -ne 8) { throw "30C.3 execution Ledger count changed" }
if ([int]$E.SHARED_RESOURCE -ne 2) { throw "30C.3 share Ledger count changed" }
if ([int]$E.SOCIAL_WARNING_ISSUED -ne 1) { throw "30C.3 warning Ledger count changed" }
if ([int]$E.SOCIAL_RECRUITMENT_OFFERED -ne 2) { throw "30C.3 recruitment offer Ledger count changed" }
if ([int]$E.SOCIAL_RECRUITMENT_ACCEPTED -ne 1) { throw "30C.3 recruitment acceptance Ledger count changed" }
if ([int]$E.SOCIAL_RECRUITMENT_REFUSED -ne 1) { throw "30C.3 recruitment refusal Ledger count changed" }
if ([int]$E.SOCIAL_CHALLENGE_ISSUED -ne 1) { throw "30C.3 challenge Ledger count changed" }
if ([int]$E.SOCIAL_MEMORY_RECORDED -lt 1 -or [int]$E.SOCIAL_MEMORY_REINFORCED -lt 1) {
  throw "30C.3 sharing did not exercise 30C.2 memory creation/reinforcement"
}

$A = $P.authority_contract
if ($A.social_proposal_is_advisory -ne $true -or $A.simulation_validates_social_legality -ne $true) {
  throw "30C.3 proposal/validation authority contract changed"
}
if ($A.simulation_executes_social_mutation -ne $true -or $A.stale_or_rejected_proposals_are_side_effect_free -ne $true) {
  throw "30C.3 execution/rejection authority contract changed"
}
if ($A.item_sharing_uses_canonical_item_ownership -ne $true -or $A.supply_sharing_preserves_30a4_authority -ne $true) {
  throw "30C.3 item/supply authority contract changed"
}
if ($A.sharing_feeds_30c2_memory -ne $true -or $A.warning_shares_only_known_sector_state -ne $true) {
  throw "30C.3 memory/warning integration contract changed"
}
if ($A.recruitment_does_not_create_party -ne $true -or $A.persistent_party_owner_slice -ne "30C.4") {
  throw "30C.3 party phase boundary changed"
}
if ($A.challenge_does_not_start_combat -ne $true -or $A.social_conflict_owner_slice -ne "30C.5") {
  throw "30C.3 conflict phase boundary changed"
}
if ($A.presentation_can_mutate -ne $false -or $A.unreal_can_mutate -ne $false) {
  throw "30C.3 presentation authority boundary changed"
}
if ($A.dialogue_owner_phase -ne "31") {
  throw "30C.3 absorbed Phase 31 dialogue scope"
}
if ($A.next_slice -notlike "30C.4*") {
  throw "30C.3 next canonical slice changed"
}

Write-Host "[30C.3] Deterministic social intent execution proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) executions=$($P.execution_count) offers=$($P.recruitment_offer_count)"
Write-Host "shareMemory=$($P.shared_memory_reinforcement_count) trust=$($P.receiver_trust) gratitude=$($P.receiver_gratitude)"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count)"
Write-Host "traceDigest=$($P.interaction_trace_digest)"

Write-Host "[30C.3] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30C.3] PASS"
Write-Host "Proof: $Proof"
