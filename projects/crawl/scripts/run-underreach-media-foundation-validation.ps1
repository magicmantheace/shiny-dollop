$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-media-foundation-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_2"
$Proof = Join-Path $Out "media-foundation-proof.json"
$Repro = Join-Path $Out "media-foundation-proof-repro.json"
$Seed = "underreach-30-5-2-media-foundation-proof"

Write-Host "[30.5.2] Accepted 30A.1-30.5.1 regressions + focused media-foundation tests"
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
  tests/test_underreach_30_5_1_canonical_media_event_export.py `
  tests/test_underreach_30_5_2_media_db_durable_queue_provider_router.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.2] Running deterministic file-backed media foundation proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.media-foundation-proof.v1") { throw "30.5.2 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.media-foundation.v1") { throw "30.5.2 slice protocol changed" }
if ($P.implementation_version -ne "30.5.2") { throw "30.5.2 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.2 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.2 media snapshot reproducibility mismatch" }
if ($P.media.database_backend -ne "sqlite") { throw "30.5.2 accepted media backend changed" }
if ($P.media.snapshot_equal_after_reopen -ne $true) { throw "30.5.2 media snapshot changed after SQLite reopen" }
if ([int]$P.media.envelope_count -ne 1) { throw "30.5.2 duplicated envelope registration" }
if ([int]$P.media.job_count -ne 3) { throw "30.5.2 durable job count changed" }
if ([int]$P.media.attempt_count -ne 3) { throw "30.5.2 durable attempt count changed" }
if ([int]$P.media.artifact_count -ne 1) { throw "30.5.2 artifact provenance probe missing" }
if ([int]$P.media.provider_execution_count -ne 0) { throw "30.5.2 routing invoked/recorded a provider execution" }

$C = $P.canonical
if ($C.state_unchanged -ne $true -or $C.fingerprint_unchanged -ne $true) { throw "30.5.2 changed canonical state" }
if ($C.history_unchanged -ne $true -or $C.ledger_rows_unchanged -ne $true) { throw "30.5.2 changed canonical Ledger history" }

$A = $P.authority_contract
if ($A.authoritative -ne $false) { throw "30.5.2 media database became authoritative" }
if ($A.canonical_owner -ne "deterministic_simulation") { throw "30.5.2 canonical owner changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.2 presentation gained simulation authority" }
if ($A.unreal_dependency -ne $false) { throw "30.5.2 added Unreal dependency" }
if ($A.required_cloud_api -ne $false -or $A.required_paid_provider -ne $false) { throw "30.5.2 added required cloud/paid dependency" }

$J = $P.queue
if ($J.duplicate_primary_same_job -ne $true) { throw "30.5.2 idempotent job enqueue failed" }
if ([int]$J.recovered_interrupted_count -ne 1) { throw "30.5.2 restart recovery count changed" }
if ($J.recovered_status -ne "retry") { throw "30.5.2 interrupted job did not recover to retry" }
if ([int]$J.first_attempt_number -ne 1 -or [int]$J.second_attempt_number -ne 2) { throw "30.5.2 attempt numbering changed across restart" }
if ($J.first_attempt_id -eq $J.second_attempt_id) { throw "30.5.2 restart reused attempt identity" }
if ($J.dependency_completed -ne $true) { throw "30.5.2 dependency release/completion failed" }
$statuses = @($J.attempt_statuses)
if (($statuses | Where-Object { $_ -eq "interrupted" }).Count -ne 1) { throw "30.5.2 interrupted attempt provenance missing" }
if (($statuses | Where-Object { $_ -eq "completed" }).Count -ne 2) { throw "30.5.2 completed attempt provenance changed" }

$R = $P.providers
if ($R.default_local_selected -ne $true) { throw "30.5.2 local provider preference failed" }
if ($R.image_vram_filter_selected -ne $true) { throw "30.5.2 VRAM capability filtering failed" }
if ($R.paid_blocked_by_default -ne $true) { throw "30.5.2 paid provider was not blocked by default" }
if ($R.paid_selected_only_with_explicit_policy -ne $true) { throw "30.5.2 explicit optional paid routing failed" }
if ($R.paid_over_budget_blocked -ne $true) { throw "30.5.2 paid budget enforcement failed" }
if ([int]$R.paid_selection_cost_microusd -le 0) { throw "30.5.2 paid provider cost metadata missing" }
if ($R.routing_invoked_provider -ne $false) { throw "30.5.2 provider router invoked a provider" }

Write-Host "[30.5.2] Durable media DB / queue / provider routing proof PASS"
Write-Host "digest=$($P.digest) snapshot=$($P.media.snapshot_digest) jobs=$($P.media.job_count) attempts=$($P.media.attempt_count)"
Write-Host "restartRecovered=$($J.recovered_interrupted_count) local=$($R.default_local_selected) paidDefaultBlocked=$($R.paid_blocked_by_default)"

Write-Host "[30.5.2] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.2] PASS"
Write-Host "Proof: $Proof"