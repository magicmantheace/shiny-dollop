$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-brain-driven-descent-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30b3"
$Proof = Join-Path $Out "brain-driven-descent-proof.json"
$Repro = Join-Path $Out "brain-driven-descent-proof-repro.json"
$Seed = "underreach-30b3-brain-driven-descent-proof"

Write-Host "[30B.3] Accepted 30A.1-30B.2 regressions + focused brain-driven orchestration tests"
& $Python -m pytest -q `
  tests/test_underreach_30a1_descent_run_state.py `
  tests/test_underreach_30a2_multi_stratum_progression.py `
  tests/test_underreach_30a3_loot_cache_relic.py `
  tests/test_underreach_30a4_resources_survival.py `
  tests/test_underreach_30a5_full_autonomous_descent.py `
  tests/test_underreach_30b1_ai_brain_foundation.py `
  tests/test_underreach_30b2_intent_validation_execution_bridge.py `
  tests/test_underreach_30b3_brain_driven_descent_orchestration.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30B.3] Running deterministic four-Stratum brain-driven proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 12 --strata 4 --max-steps 2500
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 12 --strata 4 --max-steps 2500
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.brain-driven-descent-proof.v1") {
  throw "30B.3 proof protocol changed"
}
if ($P.slice_protocol -ne "underreach.brain-driven-descent.v1") {
  throw "30B.3 slice protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30B.3 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30B.3 deterministic Descent identity mismatch"
}
if ($P.authoritative -ne $true -or $P.brain_provider_can_mutate -ne $false -or $P.presentation_feedback_allowed -ne $false) {
  throw "30B.3 authority boundary changed"
}
if ([int]$P.population_count -ne 12 -or [int]$P.configured_stratum_count -ne 4) {
  throw "30B.3 acceptance population/Stratum shape changed"
}
if ($P.final_status -ne "completed" -or $P.final_outcome -ne "completed") {
  throw "30B.3 brain-driven unattended Descent did not complete"
}
if ([int]$P.final_current_stratum_index -ne 3) {
  throw "30B.3 did not finish on Stratum index 3"
}
if ([int]$P.surviving_descender_count -lt 1) {
  throw "30B.3 completed without a surviving Descender"
}
if ([int]$P.step_count -lt 1 -or [int]$P.final_tick -lt 1) {
  throw "30B.3 brain-driven execution did not advance"
}
if ([int]$P.brain_cadence_steps -ne 1) {
  throw "30B.3 brain cadence changed"
}

$M = $P.metrics
if ([int]$M.brain_proposals -lt 1) { throw "30B.3 did not request brain proposals" }
if ([int]$M.brain_executions -lt 1) { throw "30B.3 did not execute validated brain proposals" }
if ([int]$M.brain_moves -lt 1) { throw "30B.3 brain proposals never produced canonical movement" }
if ([int]$M.brain_executions -gt [int]$M.brain_proposals) { throw "30B.3 executed more brain intents than were proposed" }
if ([int]$M.provider_errors -ne 0) { throw "30B.3 reference provider unexpectedly errored" }

$S = $P.source_autonomous_metrics
if ([int]$S.moves -lt 1) { throw "30B.3 accepted autonomous source recorded no movement" }
if ([int]$S.encounters_resolved -lt 1) { throw "30B.3 did not resolve canonical encounters" }
if ([int]$S.strata_advanced -ne 3) { throw "30B.3 did not advance all three Stratum transitions" }
if ([int]$S.cache_opens -lt 1) { throw "30B.3 did not discover/open canonical cache content" }
if ([int]$S.loot_claims -lt 1) { throw "30B.3 did not acquire canonical loot" }
if ([int]$S.supply_claims -lt 1) { throw "30B.3 did not acquire survival supplies" }
if ([int]$S.supply_consumptions -lt 1) { throw "30B.3 did not consume survival supplies" }

if ([int]$P.brain_action_counts.seek_cache -lt 1) {
  throw "30B.3 reference brain did not exercise cache-seeking intent"
}

if ($P.final_snapshot_digest -ne $P.reproduction_snapshot_digest) {
  throw "30B.3 independent reproduction final snapshot mismatch"
}
if ($P.final_canonical_fingerprint -ne $P.reproduction_canonical_fingerprint) {
  throw "30B.3 independent reproduction canonical fingerprint mismatch"
}
if ($P.final_snapshot_digest -ne $P.resumed_final_snapshot_digest) {
  throw "30B.3 checkpoint-resumed final snapshot mismatch"
}
if ($P.final_canonical_fingerprint -ne $P.resumed_final_canonical_fingerprint) {
  throw "30B.3 checkpoint-resumed canonical fingerprint mismatch"
}
if ([int]$P.checkpoint_step_count -lt 1 -or [int]$P.checkpoint_event_count -lt 1 -or -not $P.checkpoint_digest) {
  throw "30B.3 checkpoint proof is incomplete"
}

$O = $P.outage_probe
if ($O.tick_advanced -ne $true) { throw "30B.3 provider outage stalled the canonical clock" }
if ([int]$O.provider_errors -lt 1) { throw "30B.3 provider outage was not observed" }
if ([int]$O.fallback_invocations -lt 1) { throw "30B.3 provider outage did not invoke deterministic fallback" }
if ([int]$O.decision_count -lt 1) { throw "30B.3 provider outage probe did not process Descenders" }

$E = $P.event_type_counts
if ([int]$E.BRAIN_DRIVEN_DESCENT_INITIALIZED -ne 1) { throw "30B.3 brain-driven initialization event count changed" }
if ([int]$E.BRAIN_DRIVEN_DESCENT_STARTED -ne 1) { throw "30B.3 brain-driven start event count changed" }
if ([int]$E.BRAIN_DRIVEN_DESCENT_COMPLETED -ne 1) { throw "30B.3 brain-driven completion event count changed" }
if ([int]$E.BRAIN_DRIVEN_STEP_RESOLVED -ne [int]$P.step_count) { throw "30B.3 brain-driven step Ledger count changed" }
if ([int]$E.AUTONOMOUS_STEP_RESOLVED -ne [int]$P.step_count) { throw "30B.3 accepted 30A.5 step Ledger count changed" }
if ([int]$E.BRAIN_INTENT_EXECUTED -ne [int]$M.brain_executions) { throw "30B.3 brain execution Ledger count disagrees with metrics" }
if ([int]$E.SURVIVAL_TIME_APPLIED -lt [int]$P.step_count) { throw "30B.3 did not preserve the accepted survival clock" }
if ([int]$E.STRATUM_ADVANCED -ne 3) { throw "30B.3 canonical Stratum transition count changed" }

$A = $P.authority_contract
if ($A.brain_proposes_only -ne $true -or $A.brain_execution_requires_30b2_membrane -ne $true) {
  throw "30B.3 brain/execution authority contract changed"
}
if ($A.simulation_owns_time -ne $true -or $A.simulation_owns_encounters -ne $true) {
  throw "30B.3 simulation time/encounter authority changed"
}
if ($A.simulation_owns_loot_and_survival -ne $true -or $A.simulation_owns_stratum_progression -ne $true) {
  throw "30B.3 simulation loot/survival/progression authority changed"
}
if ($A.provider_failure_uses_deterministic_fallback -ne $true -or $A.nonprogress_navigation_uses_deterministic_fallback -ne $true) {
  throw "30B.3 deterministic fallback contract changed"
}
if ($A.checkpoint_resume_must_match_uninterrupted -ne $true) {
  throw "30B.3 checkpoint determinism contract changed"
}
if ($A.unreal_can_mutate -ne $false -or $A.presentation_can_mutate -ne $false) {
  throw "30B.3 presentation authority boundary changed"
}

Write-Host "[30B.3] Deterministic brain-driven Descent proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) population=$($P.population_count) strata=$($P.configured_stratum_count) steps=$($P.step_count) tick=$($P.final_tick)"
Write-Host "survivors=$($P.surviving_descender_count) eliminated=$($P.eliminated_descender_count) proposals=$($M.brain_proposals) executions=$($M.brain_executions) brainMoves=$($M.brain_moves) fallbacks=$($M.fallback_invocations)"
Write-Host "encounters=$($S.encounters_resolved) caches=$($S.cache_opens) suppliesConsumed=$($S.supply_consumptions)"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count) checkpointStep=$($P.checkpoint_step_count)"
Write-Host "traceDigest=$($P.final_step_trace_digest)"
Write-Host "completed=$($P.final_snapshot_digest)"

Write-Host "[30B.3] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30B.3] PASS"
Write-Host "Proof: $Proof"
