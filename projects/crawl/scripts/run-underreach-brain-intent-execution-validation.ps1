$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-brain-intent-execution-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30b2"
$Proof = Join-Path $Out "brain-intent-execution-proof.json"
$Repro = Join-Path $Out "brain-intent-execution-proof-repro.json"
$Seed = "underreach-30b2-intent-execution-proof"

Write-Host "[30B.2] Accepted 30A.1-30B.1 regressions + focused intent execution tests"
& $Python -m pytest -q `
  tests/test_underreach_30a1_descent_run_state.py `
  tests/test_underreach_30a2_multi_stratum_progression.py `
  tests/test_underreach_30a3_loot_cache_relic.py `
  tests/test_underreach_30a4_resources_survival.py `
  tests/test_underreach_30a5_full_autonomous_descent.py `
  tests/test_underreach_30b1_ai_brain_foundation.py `
  tests/test_underreach_30b2_intent_validation_execution_bridge.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30B.2] Running deterministic intent validation/execution proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.brain-intent-execution-proof.v1") {
  throw "30B.2 proof protocol changed"
}
if ($P.slice_protocol -ne "underreach.brain-intent-execution.v1") {
  throw "30B.2 slice protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30B.2 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30B.2 deterministic Descent identity mismatch"
}
if ([int]$P.population_count -ne 8 -or [int]$P.configured_stratum_count -ne 3) {
  throw "30B.2 proof shape changed"
}
if ($P.authoritative -ne $true -or $P.canonical_owner -ne "deterministic_simulation") {
  throw "30B.2 simulation authority changed"
}
if ($P.brain_provider_can_mutate -ne $false -or $P.validation_can_mutate -ne $false -or $P.rejected_intent_can_mutate -ne $false) {
  throw "30B.2 advisory/rejection authority boundary changed"
}
if ($P.accepted_execution_can_mutate -ne $true -or $P.presentation_feedback_allowed -ne $false) {
  throw "30B.2 execution/presentation authority boundary changed"
}
if (-not $P.initial_proposal_id -or -not $P.initial_observation_digest -or -not $P.initial_decision_digest) {
  throw "30B.2 proposal/decision binding is incomplete"
}
if (-not $P.initial_execution_result_digest -or -not $P.initial_execution_event_id) {
  throw "30B.2 accepted execution is not canonically bound"
}
if ($P.canonical_state_digest_before_execution -eq $P.canonical_state_digest_after_execution) {
  throw "30B.2 accepted execution did not change canonical state"
}
if ($P.independent_execution_equal -ne $true -or $P.independent_state_equal -ne $true) {
  throw "30B.2 independent deterministic execution diverged"
}
if ($P.stale_rejection_reason -ne "stale_observation" -or $P.stale_rejection_mutated_state -ne $false) {
  throw "30B.2 stale proposal contract changed"
}
if (-not $P.checkpoint_digest -or [int]$P.checkpoint_event_count -lt 1) {
  throw "30B.2 checkpoint proof is incomplete"
}
if ($P.checkpoint_next_proposal_equal -ne $true -or $P.checkpoint_next_execution_equal -ne $true -or $P.checkpoint_final_state_equal -ne $true) {
  throw "30B.2 checkpoint/resume execution equivalence failed"
}
if ([int]$P.event_type_counts.BRAIN_INTENT_EXECUTED -lt 2) {
  throw "30B.2 canonical brain execution Ledger events missing"
}

$A = $P.authority_contract
if ($A.brain_proposes_only -ne $true -or $A.simulation_validates_legality -ne $true -or $A.simulation_executes_mutations -ne $true) {
  throw "30B.2 proposal/validation/execution authority membrane changed"
}
if ($A.stale_or_rejected_proposals_are_side_effect_free -ne $true -or $A.execution_is_ledger_bound -ne $true) {
  throw "30B.2 rejection/Ledger contract changed"
}
if ($A.unreal_can_mutate -ne $false -or $A.presentation_can_mutate -ne $false) {
  throw "30B.2 presentation authority changed"
}
if ($A.time_cadence_owned_by_later_orchestrator -ne $true -or $A.next_slice_must_build_on_execution_membrane -ne $true) {
  throw "30B.2 scope boundary changed"
}

Write-Host "[30B.2] Deterministic intent validation/execution proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) action=$($P.initial_action)"
Write-Host "decision=$($P.initial_decision_digest) execution=$($P.initial_execution_result_digest)"
Write-Host "stale=$($P.stale_rejection_reason) checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count)"

Write-Host "[30B.2] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30B.2] PASS"
Write-Host "Proof: $Proof"
