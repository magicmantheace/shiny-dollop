$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-social-state-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30c1"
$Proof = Join-Path $Out "social-state-proof.json"
$Repro = Join-Path $Out "social-state-proof-repro.json"
$Seed = "underreach-30c1-social-state-proof"

Write-Host "[30C.1] Accepted 30A.1-30B.3 regressions + focused social-state tests"
& $Python -m pytest -q `
  tests/test_underreach_30a1_descent_run_state.py `
  tests/test_underreach_30a2_multi_stratum_progression.py `
  tests/test_underreach_30a3_loot_cache_relic.py `
  tests/test_underreach_30a4_resources_survival.py `
  tests/test_underreach_30a5_full_autonomous_descent.py `
  tests/test_underreach_30b1_ai_brain_foundation.py `
  tests/test_underreach_30b2_intent_validation_execution_bridge.py `
  tests/test_underreach_30b3_brain_driven_descent_orchestration.py `
  tests/test_underreach_30c1_social_state_foundation.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30C.1] Running deterministic social-state proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.social-state-proof.v1") {
  throw "30C.1 proof protocol changed"
}
if ($P.slice_protocol -ne "underreach.social-state.v1") {
  throw "30C.1 slice protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30C.1 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30C.1 deterministic Descent identity mismatch"
}
if ($P.social_snapshot_digest -ne $Q.social_snapshot_digest) {
  throw "30C.1 deterministic social snapshot mismatch"
}
if ($P.relationship_state_digest -ne $Q.relationship_state_digest) {
  throw "30C.1 deterministic relationship-state digest mismatch"
}
if ($P.authoritative -ne $true -or $P.canonical_owner -ne "deterministic_simulation") {
  throw "30C.1 canonical authority boundary changed"
}
if ($P.social_reasoning_can_mutate -ne $false -or $P.presentation_feedback_allowed -ne $false) {
  throw "30C.1 social/presentation mutation boundary changed"
}
if ($P.sparse_storage -ne $true) {
  throw "30C.1 sparse relationship storage changed"
}
if ([int]$P.population_count -ne 8 -or [int]$P.configured_stratum_count -ne 3) {
  throw "30C.1 acceptance population/Stratum shape changed"
}
if ([int]$P.relationship_count -ne 7) {
  throw "30C.1 deterministic sparse relationship count changed"
}
if ([int]$P.mutation_count -ne 8) {
  throw "30C.1 deterministic social mutation count changed"
}
if ($P.neutral_read_side_effect_free -ne $true) {
  throw "30C.1 neutral relationship read mutated canonical state"
}
if ($P.rejected_mutation_side_effect_free -ne $true) {
  throw "30C.1 rejected relationship mutation changed canonical state"
}
if ($P.directed_relationships_independent -ne $true -or $P.deterministic_clamping -ne $true) {
  throw "30C.1 directed relationship or clamping contract changed"
}
if ($P.independent_state_equal -ne $true -or $P.independent_snapshot_equal -ne $true -or $P.independent_event_ids_equal -ne $true) {
  throw "30C.1 independent deterministic reproduction failed"
}
if ($P.persistence_state_equal -ne $true) {
  throw "30C.1 persisted social state did not round-trip exactly"
}
if ($P.checkpoint_state_equal -ne $true -or $P.checkpoint_snapshot_equal -ne $true) {
  throw "30C.1 checkpoint-restored social state diverged"
}
if ([int]$P.checkpoint_event_count -lt 1 -or -not $P.checkpoint_digest) {
  throw "30C.1 checkpoint proof is incomplete"
}

$E = $P.event_type_counts
if ([int]$E.SOCIAL_STATE_INITIALIZED -ne 1) {
  throw "30C.1 social-state initialization Ledger count changed"
}
if ([int]$E.SOCIAL_RELATIONSHIP_CREATED -ne 1) {
  throw "30C.1 explicit relationship creation Ledger count changed"
}
if ([int]$E.SOCIAL_RELATIONSHIP_CHANGED -ne 7) {
  throw "30C.1 relationship mutation Ledger count changed"
}

$A = $P.authority_contract
if ($A.single_canonical_descent_tree -ne $true) { throw "30C.1 introduced a second social truth tree" }
if ($A.relationship_state_is_directed -ne $true) { throw "30C.1 relationship directionality changed" }
if ($A.absent_relationship_reads_neutral -ne $true -or $A.absent_read_does_not_allocate -ne $true) {
  throw "30C.1 sparse neutral-read contract changed"
}
if ($A.simulation_owns_social_mutation -ne $true -or $A.social_reasoning_can_mutate -ne $false) {
  throw "30C.1 deterministic social authority changed"
}
if ($A.mutation_is_ledger_bound -ne $true -or $A.source_event_provenance_is_structured -ne $true) {
  throw "30C.1 Ledger provenance contract changed"
}
if ($A.presentation_can_mutate -ne $false -or $A.unreal_can_mutate -ne $false) {
  throw "30C.1 presentation authority boundary changed"
}
if ($A.free_form_dialogue_is_deferred_to_phase31 -ne $true) {
  throw "30C.1 absorbed Phase 31 dialogue scope"
}
if (-not ([string]$A.next_slice).StartsWith("30C.2")) {
  throw "30C.1 next canonical slice changed"
}

Write-Host "[30C.1] Deterministic social state proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) relationships=$($P.relationship_count) mutations=$($P.mutation_count)"
Write-Host "relationshipDigest=$($P.relationship_state_digest)"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count)"

Write-Host "[30C.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30C.1] PASS"
Write-Host "Proof: $Proof"
