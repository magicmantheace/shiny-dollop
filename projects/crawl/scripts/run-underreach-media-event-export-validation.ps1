$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-media-event-export-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_1"
$Proof = Join-Path $Out "media-event-export-proof.json"
$Repro = Join-Path $Out "media-event-export-proof-repro.json"
$Seed = "underreach-30-5-1-media-export-proof"

Write-Host "[30.5.1] Accepted 30A.1-30C.6 regressions + focused media-export tests"
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
  tests/test_underreach_30_5_1_canonical_media_event_export.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.1] Running deterministic canonical media export proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 6 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 6 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.media-event-export-proof.v1") { throw "30.5.1 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.media-envelope.v1") { throw "30.5.1 slice protocol changed" }
if ($P.implementation_version -ne "30.5.1") { throw "30.5.1 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.1 proof reproducibility digest mismatch" }
if ($P.run.envelope_digest -ne $Q.run.envelope_digest) { throw "30.5.1 envelope reproducibility digest mismatch" }
if ($P.run.idempotency_key -ne $Q.run.idempotency_key) { throw "30.5.1 idempotency key mismatch" }
if ($P.run.repeat_export_equal -ne $true) { throw "30.5.1 repeat export diverged" }
if ($P.run.source_event_order_normalized -ne $true) { throw "30.5.1 source event order was not canonicalized" }
if ([int]$P.run.allowed_fact_count -lt 12) { throw "30.5.1 allowed fact coverage is too small" }
if ([int]$P.run.relationship_context_count -lt 1) { throw "30.5.1 relationship context missing" }
if ([int]$P.run.memory_context_count -lt 1) { throw "30.5.1 social memory context missing" }
if ([int]$P.run.participant_context_count -lt 2) { throw "30.5.1 participant context missing" }

if ($P.run.canonical_fingerprint_before -ne $P.run.canonical_fingerprint_after) { throw "30.5.1 changed canonical fingerprint" }
if ($P.run.canonical_state_digest_before -ne $P.run.canonical_state_digest_after) { throw "30.5.1 changed full canonical state digest" }
if ($P.run.history_digest_before -ne $P.run.history_digest_after) { throw "30.5.1 changed canonical history" }
if ($P.run.ledger_digest_before -ne $P.run.ledger_digest_after) { throw "30.5.1 changed durable Ledger rows" }
if ([int]$P.run.ledger_event_count_before -ne [int]$P.run.ledger_event_count_after) { throw "30.5.1 changed durable Ledger event count" }

if ($P.run.presentation_can_mutate_simulation -ne $false) { throw "30.5.1 presentation authority changed" }
if ($P.run.unreal_dependency -ne $false) { throw "30.5.1 added Unreal dependency" }
if ($P.run.cloud_ai_dependency -ne $false) { throw "30.5.1 added cloud AI dependency" }
if ($P.run.paid_ai_dependency -ne $false) { throw "30.5.1 added paid AI dependency" }

$A = $P.authority_contract
if ($A.simulation_is_authoritative -ne $true -or $A.export_is_read_only -ne $true) { throw "30.5.1 authority contract changed" }
if ($A.export_writes_ledger -ne $false -or $A.export_writes_canonical_state -ne $false) { throw "30.5.1 export gained canonical write authority" }
if ($A.media_database_in_slice -ne $false -or $A.provider_router_in_slice -ne $false) { throw "30.5.1 absorbed 30.5.2" }
if ($A.generated_prose_in_slice -ne $false -or $A.image_generation_in_slice -ne $false -or $A.video_generation_in_slice -ne $false) { throw "30.5.1 absorbed later media generation" }
if ($A.next_slice -notlike "30.5.2*") { throw "30.5.1 next canonical slice changed" }

Write-Host "[30.5.1] Deterministic canonical media export proof PASS"
Write-Host "digest=$($P.digest) envelope=$($P.run.envelope_digest) facts=$($P.run.allowed_fact_count)"
Write-Host "ledgerEvents=$($P.run.ledger_event_count_after) relationshipContext=$($P.run.relationship_context_count) memoryContext=$($P.run.memory_context_count)"

Write-Host "[30.5.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.1] PASS"
Write-Host "Proof: $Proof"
