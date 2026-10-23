$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-full-autonomous-descent-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30a5"
$Proof = Join-Path $Out "full-autonomous-descent-proof.json"
$Repro = Join-Path $Out "full-autonomous-descent-proof-repro.json"
$Seed = "underreach-30a5-full-autonomous-descent-proof"

Write-Host "[30A.5] Accepted 30A.1-30A.4 regressions + focused full autonomous Descent tests"
& $Python -m pytest -q `
  tests/test_underreach_30a1_descent_run_state.py `
  tests/test_underreach_30a2_multi_stratum_progression.py `
  tests/test_underreach_30a3_loot_cache_relic.py `
  tests/test_underreach_30a4_resources_survival.py `
  tests/test_underreach_30a5_full_autonomous_descent.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30A.5] Running deterministic four-Stratum unattended Descent proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 12 --strata 4 --max-steps 2500
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 12 --strata 4 --max-steps 2500
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.full-autonomous-descent-proof.v1") {
  throw "30A.5 proof protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30A.5 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30A.5 deterministic Descent identity mismatch"
}
if ($P.authoritative -ne $true -or $P.presentation_feedback_allowed -ne $false) {
  throw "30A.5 authority boundary changed"
}
if ([int]$P.population_count -ne 12 -or [int]$P.configured_stratum_count -ne 4) {
  throw "30A.5 acceptance population/Stratum shape changed"
}
if ($P.final_status -ne "completed" -or $P.final_outcome -ne "completed") {
  throw "30A.5 unattended Descent did not complete"
}
if ([int]$P.final_current_stratum_index -ne 3) {
  throw "30A.5 did not finish on Stratum index 3"
}
if ([int]$P.surviving_descender_count -lt 1) {
  throw "30A.5 completed without a surviving Descender"
}
if ([int]$P.step_count -lt 1 -or [int]$P.final_tick -lt 1) {
  throw "30A.5 autonomous execution did not advance"
}

$M = $P.metrics
if ([int]$M.moves -lt 1) { throw "30A.5 did not autonomously move Descenders" }
if ([int]$M.encounters_resolved -lt 1) { throw "30A.5 did not resolve autonomous encounters" }
if ([int]$M.strata_advanced -ne 3) { throw "30A.5 did not autonomously advance all three Stratum transitions" }
if ([int]$M.cache_opens -lt 1) { throw "30A.5 did not autonomously discover/open a cache" }
if ([int]$M.loot_claims -lt 1) { throw "30A.5 did not autonomously acquire cache/ground loot" }
if ([int]$M.supply_claims -lt 1) { throw "30A.5 did not autonomously acquire survival supplies" }
if ([int]$M.supply_consumptions -lt 1) { throw "30A.5 did not autonomously consume a survival supply" }

if ([int]$P.action_counts.explore -lt 1) { throw "30A.5 bounded policy did not exercise exploration" }
if ([int]$P.action_counts.seek_exit -lt 1) { throw "30A.5 bounded policy did not exercise exit-seeking" }

if ($P.final_snapshot_digest -ne $P.reproduction_snapshot_digest) {
  throw "30A.5 independent reproduction final snapshot mismatch"
}
if ($P.final_canonical_fingerprint -ne $P.reproduction_canonical_fingerprint) {
  throw "30A.5 independent reproduction canonical fingerprint mismatch"
}
if ($P.final_snapshot_digest -ne $P.resumed_final_snapshot_digest) {
  throw "30A.5 checkpoint-resumed final snapshot mismatch"
}
if ($P.final_canonical_fingerprint -ne $P.resumed_final_canonical_fingerprint) {
  throw "30A.5 checkpoint-resumed canonical fingerprint mismatch"
}
if ([int]$P.checkpoint_stratum_index -ne 1) {
  throw "30A.5 checkpoint was not captured on Stratum index 1"
}
if ([int]$P.checkpoint_step_count -lt 1 -or [int]$P.checkpoint_event_count -lt 1 -or -not $P.checkpoint_digest) {
  throw "30A.5 checkpoint proof is incomplete"
}
if ($P.portable_restored_canonical_fingerprint -ne $P.checkpoint_canonical_fingerprint) {
  throw "30A.5 portable/checkpoint restored checkpoint fingerprints disagree"
}

$E = $P.event_type_counts
if ([int]$E.AUTONOMOUS_STEP_RESOLVED -lt 1) { throw "30A.5 canonical autonomous step Ledger events missing" }
if ([int]$E.FULL_AUTONOMOUS_DESCENT_STARTED -ne 1) { throw "30A.5 autonomous start event count changed" }
if ([int]$E.FULL_AUTONOMOUS_DESCENT_COMPLETED -ne 1) { throw "30A.5 autonomous completion event count changed" }
if ([int]$E.SURVIVAL_TIME_APPLIED -lt 1) { throw "30A.5 did not use the accepted 30A.4 survival clock" }
if ([int]$E.STRATUM_ADVANCED -ne 3) { throw "30A.5 canonical 30A.2 transition Ledger count changed" }

$Authority = $P.authority_contract
if ($Authority.simulation_decides_truth -ne $true -or $Authority.unreal_can_mutate -ne $false -or $Authority.presentation_can_mutate -ne $false) {
  throw "30A.5 simulation/presentation authority contract changed"
}
if ($Authority.resource_clock_owned_by_30a4 -ne $true -or $Authority.autonomous_policy_is_bounded -ne $true) {
  throw "30A.5 accepted source/policy boundary changed"
}
if ($Authority.checkpoint_resume_must_match_uninterrupted -ne $true) {
  throw "30A.5 checkpoint determinism contract changed"
}
if ($Authority.next_phase_owned_by -ne "30B") {
  throw "30A.5 crossed the next canonical phase boundary"
}

Write-Host "[30A.5] Deterministic full autonomous Descent proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) population=$($P.population_count) strata=$($P.configured_stratum_count) steps=$($P.step_count) tick=$($P.final_tick)"
Write-Host "survivors=$($P.surviving_descender_count) eliminated=$($P.eliminated_descender_count) encounters=$($M.encounters_resolved) caches=$($M.cache_opens) suppliesConsumed=$($M.supply_consumptions)"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count) checkpointStep=$($P.checkpoint_step_count)"
Write-Host "traceDigest=$($P.step_trace_digest)"
Write-Host "completed=$($P.final_snapshot_digest)"

Write-Host "[30A.5] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30A.5] PASS"
Write-Host "Proof: $Proof"
