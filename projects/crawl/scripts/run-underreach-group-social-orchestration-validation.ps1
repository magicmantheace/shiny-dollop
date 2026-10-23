$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-group-social-orchestration-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30c6"
$Proof = Join-Path $Out "group-social-orchestration-proof.json"
$Repro = Join-Path $Out "group-social-orchestration-proof-repro.json"
$SeedBase = "underreach-30c6-group-social-proof"

Write-Host "[30C.6] Accepted 30A.1-30C.5 regressions + focused group-social tests"
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
  tests/test_underreach_30c6_alliance_conflict_direction.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30C.6] Running deterministic multi-seed group-social proof twice"
& $Python $Generator --output $Proof --seed-base $SeedBase --seed-count 3 --count 10 --strata 3 --gameplay-steps 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed-base $SeedBase --seed-count 3 --count 10 --strata 3 --gameplay-steps 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.group-social-orchestration-proof.v1") { throw "30C.6 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.group-social-orchestration.v1") { throw "30C.6 slice protocol changed" }
if ($P.digest -ne $Q.digest) { throw "30C.6 proof reproducibility digest mismatch" }
if ($P.run_digest -ne $Q.run_digest) { throw "30C.6 multi-seed run digest mismatch" }
if ($P.authoritative -ne $true -or $P.canonical_owner -ne "deterministic_simulation") { throw "30C.6 authority boundary changed" }
if ($P.presentation_feedback_allowed -ne $false -or $P.dialogue_enabled -ne $false) { throw "30C.6 presentation/dialogue boundary changed" }
if ($P.random_social_actions_allowed -ne $false) { throw "30C.6 introduced random social actions" }
if ([int]$P.seed_count -ne 3 -or [int]$P.population_count -ne 10 -or [int]$P.configured_stratum_count -ne 3) { throw "30C.6 multi-seed proof shape changed" }
if ([int]$P.total_social_steps -lt 6 -or [int]$P.total_gameplay_steps -lt 3) { throw "30C.6 unattended runtime coverage is too small" }
if ($P.all_checkpoint_roundtrips_equal -ne $true) { throw "30C.6 checkpoint/replay roundtrip diverged" }
if ($P.all_hostile_alliance_breaks_proven -ne $true) { throw "30C.6 hostile alliance-break provenance missing" }

$M = $P.aggregate_metrics
if ([int]$M.party_formations -lt 3) { throw "30C.6 did not form parties autonomously across seeds" }
if ([int]$M.party_dissolutions -lt 3) { throw "30C.6 did not dissolve parties autonomously across seeds" }
if ([int]$M.leadership_changes -lt 6) { throw "30C.6 deterministic leadership-shift coverage changed" }
if ([int]$M.alliance_formations -lt 3) { throw "30C.6 autonomous alliance formation coverage changed" }
if ([int]$M.conflict_attempts -lt 6 -or [int]$M.hostile_conflicts -lt 6) { throw "30C.6 evidence-gated social-conflict coverage changed" }

$S = $P.aggregate_strategy_counts
$strategyModes = 0
foreach ($name in @("cooperative", "balanced", "selfish")) {
  if ([int]$S.$name -gt 0) { $strategyModes += 1 }
}
if ($strategyModes -lt 2) { throw "30C.6 proof did not exhibit multiple social strategy modes" }

foreach ($Run in $P.runs) {
  if ([int]$Run.social_step_count -lt 2) { throw "30C.6 seed run lacks social-step history" }
  if ([int]$Run.gameplay_steps_executed -lt 1) { throw "30C.6 seed run did not continue accepted gameplay" }
  if ($Run.checkpoint_state_equal -ne $true -or $Run.checkpoint_snapshot_equal -ne $true) { throw "30C.6 seed checkpoint restore diverged" }
  if ($Run.hostile_alliance_break_recorded -ne $true) { throw "30C.6 seed lost hostile alliance-break record" }
  if (-not $Run.snapshot_digest -or -not $Run.canonical_fingerprint -or -not $Run.checkpoint_digest) { throw "30C.6 seed proof digests are incomplete" }
}

$E = $P.aggregate_event_type_counts
if ([int]$E.GROUP_SOCIAL_ORCHESTRATION_INITIALIZED -ne 3) { throw "30C.6 initialization Ledger count changed" }
if ([int]$E.GROUP_SOCIAL_ORCHESTRATION_STEP_RESOLVED -lt 6) { throw "30C.6 social-step Ledger coverage changed" }
if ([int]$E.SOCIAL_PARTY_FORMED -lt 3) { throw "30C.6 party formation Ledger coverage changed" }
if ([int]$E.SOCIAL_PARTY_LEADER_CHANGED -lt 6) { throw "30C.6 leadership Ledger coverage changed" }
if ([int]$E.SOCIAL_ALLIANCE_FORMED -lt 3) { throw "30C.6 alliance Ledger coverage changed" }
if ([int]$E.ALLIANCE_BETRAYAL -lt 3) { throw "30C.6 hostile alliance conflict Ledger coverage changed" }

$A = $P.authority_contract
if ($A.social_strategy_is_deterministic -ne $true -or $A.orchestrator_composes_existing_mutation_services -ne $true) { throw "30C.6 orchestration authority contract changed" }
if ($A.recruitment_uses_30c3 -ne $true -or $A.parties_and_alliances_use_30c4 -ne $true) { throw "30C.6 30C.3/30C.4 ownership boundary changed" }
if ($A.betrayal_and_hostile_conflict_use_30c5 -ne $true -or $A.random_betrayal_allowed -ne $false) { throw "30C.6 30C.5 conflict boundary changed" }
if ($A.brain_gameplay_authority_remains_30b3 -ne $true) { throw "30C.6 stole gameplay authority from 30B.3" }
if ($A.social_history_survives_checkpoint_replay -ne $true) { throw "30C.6 social-history persistence contract changed" }
if ($A.presentation_can_mutate -ne $false -or $A.unreal_can_mutate -ne $false) { throw "30C.6 presentation authority changed" }
if ($A.dialogue_owner_phase -ne "31") { throw "30C.6 absorbed Phase 31 dialogue" }
if ($A.phase_30c_complete -ne $true) { throw "30C.6 no longer closes Phase 30C" }
if ($A.next_phase -notlike "31*") { throw "30C.6 next canonical phase changed" }

Write-Host "[30C.6] Deterministic multi-seed group-social orchestration proof PASS"
Write-Host "digest=$($P.digest) seeds=$($P.seed_count) socialSteps=$($P.total_social_steps) gameplaySteps=$($P.total_gameplay_steps)"
Write-Host "partyFormations=$($M.party_formations) dissolutions=$($M.party_dissolutions) leadership=$($M.leadership_changes) alliances=$($M.alliance_formations)"
Write-Host "conflictAttempts=$($M.conflict_attempts) hostileConflicts=$($M.hostile_conflicts)"
Write-Host "runDigest=$($P.run_digest)"

Write-Host "[30C.6] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30C.6] PASS"
Write-Host "Proof: $Proof"
