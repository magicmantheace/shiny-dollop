$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-social-memory-evolution-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30c2"
$Proof = Join-Path $Out "social-memory-evolution-proof.json"
$Repro = Join-Path $Out "social-memory-evolution-proof-repro.json"
$Seed = "underreach-30b3-brain-driven-descent-proof"

Write-Host "[30C.2] Accepted 30A.1-30C.1 regressions + focused social-memory tests"
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
  tests/test_underreach_30c2_social_memory_relationship_evolution.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30C.2] Running deterministic social-memory evolution proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 12 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 12 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.social-memory-evolution-proof.v1") {
  throw "30C.2 proof protocol changed"
}
if ($P.slice_protocol -ne "underreach.social-memory-evolution.v1") {
  throw "30C.2 slice protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30C.2 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30C.2 deterministic Descent identity mismatch"
}
if ($P.final_memory_state_digest -ne $Q.final_memory_state_digest) {
  throw "30C.2 deterministic memory-state digest mismatch"
}
if ($P.final_relationship_state_digest -ne $Q.final_relationship_state_digest) {
  throw "30C.2 deterministic relationship-state digest mismatch"
}
if ($P.authoritative -ne $true -or $P.canonical_owner -ne "deterministic_simulation") {
  throw "30C.2 canonical authority boundary changed"
}
if ($P.social_reasoning_can_mutate -ne $false -or $P.narrative_can_create_memory -ne $false) {
  throw "30C.2 social/narrative mutation boundary changed"
}
if ($P.presentation_feedback_allowed -ne $false -or $P.relationship_time_decay_enabled -ne $false) {
  throw "30C.2 presentation or relationship-decay boundary changed"
}
if ([int]$P.population_count -ne 12 -or [int]$P.configured_stratum_count -ne 4) {
  throw "30C.2 acceptance population/Stratum shape changed"
}
if ([int]$P.source_event_count -ne 6 -or [int]$P.processed_source_event_count -ne 6) {
  throw "30C.2 source-event processing count changed"
}
if ([int]$P.social_fact_count -ne 7) {
  throw "30C.2 deterministic social-fact count changed"
}
if ([int]$P.memory_count -ne 6 -or [int]$P.memory_event_count -ne 7) {
  throw "30C.2 memory/reinforcement count changed"
}
if ([int]$P.relationship_count -ne 5) {
  throw "30C.2 sparse relationship count changed"
}
if ([int]$P.relationship_mutation_event_count -ne 28) {
  throw "30C.2 deterministic relationship mutation count changed"
}
if ($P.duplicate_processing_side_effect_free -ne $true) {
  throw "30C.2 duplicate source processing mutated canonical state"
}
if ([int]$P.later_stratum_number -lt 2 -or [int]$P.steps_to_later_stratum -lt 1) {
  throw "30C.2 proof did not cross a real Stratum boundary"
}
if ($P.cross_stratum_relationship_equal -ne $true -or $P.cross_stratum_memory_sources_equal -ne $true) {
  throw "30C.2 social history did not survive Stratum progression"
}
if ([int]$P.decay_affected_memory_count -lt 1 -or [int]$P.decay_changed_memory_count -lt 1) {
  throw "30C.2 bounded memory decay did not execute"
}
if ($P.decay_reduced_salience -ne $true -or $P.relationship_unchanged_by_decay -ne $true) {
  throw "30C.2 memory decay changed relationship truth or failed to reduce salience"
}
if ($P.independent_source_ids_equal -ne $true -or $P.independent_memory_equal -ne $true) {
  throw "30C.2 source-history replay memory reconstruction diverged"
}
if ($P.independent_social_equal -ne $true -or $P.independent_state_equal -ne $true) {
  throw "30C.2 independent deterministic canonical state diverged"
}
if ($P.checkpoint_state_equal -ne $true -or $P.checkpoint_memory_equal -ne $true -or $P.checkpoint_social_equal -ne $true) {
  throw "30C.2 checkpoint-restored social state diverged"
}
if ([int]$P.checkpoint_event_count -lt 1 -or -not $P.checkpoint_digest) {
  throw "30C.2 checkpoint proof is incomplete"
}

$E = $P.event_type_counts
if ([int]$E.SOCIAL_MEMORY_EVOLUTION_INITIALIZED -ne 1) {
  throw "30C.2 initialization Ledger count changed"
}
if ([int]$E.SOCIAL_MEMORY_RECORDED -ne 6) {
  throw "30C.2 memory-recorded Ledger count changed"
}
if ([int]$E.SOCIAL_MEMORY_REINFORCED -ne 1) {
  throw "30C.2 reinforcement Ledger count changed"
}
if ([int]$E.SOCIAL_MEMORY_DECAY_APPLIED -ne 1) {
  throw "30C.2 memory-decay Ledger count changed"
}
if ([int]$E.SOCIAL_RELATIONSHIP_CHANGED -ne 28) {
  throw "30C.2 30C.1 relationship Ledger count changed"
}

$A = $P.authority_contract
if ($A.single_canonical_descent_tree -ne $true -or $A.memory_requires_real_ledger_event -ne $true) {
  throw "30C.2 canonical memory ownership changed"
}
if ($A.duplicate_source_processing_is_side_effect_free -ne $true -or $A.source_events_processed_in_ledger_order -ne $true) {
  throw "30C.2 source-event processing contract changed"
}
if ($A.relationship_mutation_uses_30c1_service -ne $true -or $A.memory_decay_does_not_change_relationship_truth -ne $true) {
  throw "30C.2 relationship authority contract changed"
}
if ($A.generated_narrative_can_create_memory -ne $false -or $A.presentation_can_mutate -ne $false -or $A.unreal_can_mutate -ne $false) {
  throw "30C.2 downstream authority boundary changed"
}
if ($A.checkpoint_and_replay_are_deterministic -ne $true) {
  throw "30C.2 checkpoint/replay determinism contract changed"
}
if ($A.next_slice -ne "30C.3") {
  throw "30C.2 next canonical slice changed"
}

Write-Host "[30C.2] Deterministic social-memory evolution proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) memories=$($P.memory_count) facts=$($P.social_fact_count) laterStratum=$($P.later_stratum_number)"
Write-Host "memoryDigest=$($P.final_memory_state_digest) relationshipDigest=$($P.final_relationship_state_digest)"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count)"

Write-Host "[30C.2] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30C.2] PASS"
Write-Host "Proof: $Proof"
