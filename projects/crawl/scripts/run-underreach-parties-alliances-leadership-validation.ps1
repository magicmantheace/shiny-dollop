$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-parties-alliances-leadership-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30c4"
$Proof = Join-Path $Out "parties-alliances-leadership-proof.json"
$Repro = Join-Path $Out "parties-alliances-leadership-proof-repro.json"
$Seed = "underreach-30c4-parties-proof"

Write-Host "[30C.4] Accepted 30A.1-30C.3 regressions + focused parties/alliances/leadership tests"
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
  tests/test_underreach_30c4_parties_alliances_leadership.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30C.4] Running deterministic parties/alliances/leadership proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 7 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 7 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.parties-alliances-leadership-proof.v1") { throw "30C.4 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.parties-alliances-leadership.v1") { throw "30C.4 slice protocol changed" }
if ($P.digest -ne $Q.digest) { throw "30C.4 proof reproducibility digest mismatch" }
if ($P.descent_id -ne $Q.descent_id) { throw "30C.4 deterministic Descent identity mismatch" }
if ($P.final_snapshot_digest -ne $Q.final_snapshot_digest) { throw "30C.4 deterministic snapshot mismatch" }
if ($P.final_canonical_fingerprint -ne $Q.final_canonical_fingerprint) { throw "30C.4 canonical fingerprint mismatch" }
if ($P.authoritative -ne $true -or $P.canonical_owner -ne "deterministic_simulation") { throw "30C.4 authority boundary changed" }
if ($P.presentation_feedback_allowed -ne $false -or $P.betrayal_enabled -ne $false) { throw "30C.4 scope boundary changed" }
if ([int]$P.population_count -ne 7 -or [int]$P.configured_stratum_count -ne 3) { throw "30C.4 proof population/Stratum shape changed" }
if ([int]$P.consumed_recruitment_offer_count -ne 3) { throw "30C.4 recruitment materialization count changed" }
if ([int]$P.total_party_count -ne 2 -or [int]$P.active_party_count -ne 1) { throw "30C.4 party lifecycle count changed" }
if ($P.left_party_active_after_disband -ne $false -or $P.right_party_active -ne $true) { throw "30C.4 disband lifecycle changed" }
if ($P.elected_leader_id -ne $P.expected_elected_leader_id -or $P.elected_leader_id -ne "descender_002") { throw "30C.4 deterministic leadership election changed" }
if ([int]$P.coordination_record_count -ne 1 -or -not $P.coordinated_destination) { throw "30C.4 coordinated movement proof changed" }
if ($P.alliance_status -ne "dissolved" -or $P.alliance_dissolution_reason -ne "strategic_separation") { throw "30C.4 alliance lifecycle changed" }
if ($P.alliance_betrayal_semantics -ne $false) { throw "30C.4 illegally absorbed betrayal semantics" }
if ($P.independent_state_equal -ne $true -or $P.independent_snapshot_equal -ne $true -or $P.independent_event_ids_equal -ne $true) { throw "30C.4 independent deterministic reproduction failed" }
if ($P.checkpoint_state_equal -ne $true -or $P.checkpoint_snapshot_equal -ne $true) { throw "30C.4 checkpoint restore diverged" }
if ([int]$P.checkpoint_event_count -lt 1 -or -not $P.checkpoint_digest) { throw "30C.4 checkpoint proof incomplete" }

$E = $P.event_type_counts
if ([int]$E.SOCIAL_PARTY_SYSTEM_INITIALIZED -ne 1) { throw "30C.4 initialization event count changed" }
if ([int]$E.SOCIAL_PARTY_FORMED -ne 2) { throw "30C.4 party formation event count changed" }
if ([int]$E.SOCIAL_PARTY_MEMBER_JOINED -ne 1) { throw "30C.4 party join event count changed" }
if ([int]$E.SOCIAL_PARTY_LEADER_CHANGED -lt 1) { throw "30C.4 leadership event missing" }
if ([int]$E.SOCIAL_PARTY_OBJECTIVE_CHANGED -ne 1) { throw "30C.4 objective event count changed" }
if ([int]$E.SOCIAL_PARTY_LOOT_POLICY_CHANGED -ne 1) { throw "30C.4 loot policy event count changed" }
if ([int]$E.SOCIAL_PARTY_POSTURE_CHANGED -ne 1) { throw "30C.4 posture event count changed" }
if ([int]$E.SOCIAL_PARTY_COORDINATED_MOVE -ne 1) { throw "30C.4 coordinated movement event count changed" }
if ([int]$E.SOCIAL_ALLIANCE_FORMED -ne 1 -or [int]$E.SOCIAL_ALLIANCE_DISSOLVED -ne 1) { throw "30C.4 alliance Ledger coverage changed" }
if ([int]$E.SOCIAL_PARTY_MEMBER_LEFT -ne 1 -or [int]$E.SOCIAL_PARTY_DISBANDED -ne 1) { throw "30C.4 leave/disband Ledger coverage changed" }

$A = $P.authority_contract
if ($A.crawl_party_is_canonical -ne $true -or $A.accepted_recruitment_materializes_party -ne $true) { throw "30C.4 party authority contract changed" }
if ($A.accepted_offer_materializes_once -ne $true -or $A.leadership_is_deterministic -ne $true) { throw "30C.4 recruitment/leadership contract changed" }
if ($A.party_policy_is_canonical -ne $true -or $A.coordinated_movement_uses_simulation_authority -ne $true) { throw "30C.4 policy/movement contract changed" }
if ($A.alliances_are_persistent_structured_state -ne $true -or $A.betrayal_owned_by_30c5 -ne $true) { throw "30C.4 alliance/30C.5 boundary changed" }
if ($A.presentation_can_mutate -ne $false -or $A.unreal_can_mutate -ne $false) { throw "30C.4 presentation authority changed" }
if ($A.dialogue_owner_phase -ne "31") { throw "30C.4 absorbed Phase 31 dialogue" }
if ($A.next_slice -notlike "30C.5*") { throw "30C.4 next canonical slice changed" }

Write-Host "[30C.4] Deterministic parties/alliances/leadership proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) parties=$($P.total_party_count) active=$($P.active_party_count)"
Write-Host "leader=$($P.elected_leader_id) offers=$($P.consumed_recruitment_offer_count) coordination=$($P.coordination_record_count)"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count)"
Write-Host "traceDigest=$($P.coordination_trace_digest)"

Write-Host "[30C.4] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30C.4] PASS"
Write-Host "Proof: $Proof"
