$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-loot-cache-relic-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30a3"
$Proof = Join-Path $Out "loot-cache-relic-proof.json"
$Repro = Join-Path $Out "loot-cache-relic-proof-repro.json"
$Seed = "underreach-30a3-loot-cache-relic-proof"

Write-Host "[30A.3] Accepted 30A.2 regression + focused loot/cache/relic tests"
& $Python -m pytest -q tests/test_underreach_30a2_multi_stratum_progression.py tests/test_underreach_30a3_loot_cache_relic.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30A.3] Generating canonical four-Stratum loot/cache/relic proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.loot-cache-relic-proof.v1") {
  throw "30A.3 proof protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30A.3 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30A.3 deterministic Descent identity mismatch"
}
if ($P.cache_generation_digest -ne $Q.cache_generation_digest) {
  throw "30A.3 deterministic cache generation digest mismatch"
}
if ($P.authoritative -ne $true -or $P.presentation_feedback_allowed -ne $false) {
  throw "30A.3 authority boundary changed"
}
if ([int]$P.population_count -ne 8 -or [int]$P.configured_stratum_count -ne 4) {
  throw "30A.3 proof population/Stratum contract changed"
}
if ([int]$P.cache_count -ne 4) {
  throw "30A.3 proof must generate exactly one deterministic cache per Stratum"
}
if ([int]$P.relic_blueprint_count -ne 4) {
  throw "30A.3 proof must generate exactly one relic blueprint per Stratum"
}
if ($P.relic_ids.Count -ne 4) {
  throw "30A.3 relic identity proof is incomplete"
}
if ([int]$P.first_cache_item_count -ne 3 -or $P.first_cache_final_status -ne "depleted") {
  throw "30A.3 first cache did not materialize/claim exactly two ordinary items plus one relic"
}
if ($P.first_relic_final_owner -ne "descender_001" -or $P.second_relic_final_owner -ne "descender_001") {
  throw "30A.3 final relic ownership proof changed"
}
if ($P.first_relic_provenance_event_ids.Count -ne 4) {
  throw "30A.3 first relic provenance must prove open -> acquire -> drop -> acquire"
}
if ($P.first_relic_acquisition_event_ids.Count -ne 2) {
  throw "30A.3 first relic must prove two canonical acquisitions"
}
if (-not $P.created_snapshot_digest -or -not $P.after_reclaim_snapshot_digest -or -not $P.after_first_transition_snapshot_digest -or -not $P.after_second_relic_snapshot_digest -or -not $P.completed_snapshot_digest) {
  throw "30A.3 lifecycle loot snapshots are incomplete"
}
if ([int]$P.alpha_checkpoint_stratum_index -ne 1) {
  throw "30A.3 checkpoint must restore on Stratum index 1 after the first transition"
}
if ([int]$P.alpha_checkpoint_event_count -lt 20) {
  throw "30A.3 checkpoint did not bind a meaningful loot/progression Ledger prefix"
}
if ($P.alpha_checkpoint_snapshot_digest -ne $P.after_first_transition_snapshot_digest) {
  throw "30A.3 checkpoint loot snapshot diverged from the post-transition canonical state"
}
$Statuses = $P.completed_cache_status_counts
if ([int]$Statuses.depleted -ne 1 -or [int]$Statuses.opened -ne 1 -or [int]$Statuses.sealed -ne 2) {
  throw "30A.3 final cache-state mix changed"
}
if ([int]$P.final_materialized_item_count -ne 6 -or [int]$P.final_owned_item_count -ne 4 -or [int]$P.final_owned_relic_count -ne 2) {
  throw "30A.3 final materialized/owned loot counts changed"
}
if ($P.final_status -ne "completed" -or [int]$P.final_current_stratum_index -ne 3) {
  throw "30A.3 proof did not finish on the fourth Stratum"
}
if (-not ($P.event_types -contains "LOOT_CACHE_RELIC_INITIALIZED") -or -not ($P.event_types -contains "CACHE_OPENED") -or -not ($P.event_types -contains "ITEM_ACQUIRED") -or -not ($P.event_types -contains "ITEM_DROPPED")) {
  throw "30A.3 canonical loot Ledger events are incomplete"
}
$Authority = $P.authority_contract
if ($Authority.simulation_decides_truth -ne $true -or $Authority.unreal_can_mutate -ne $false -or $Authority.presentation_can_mutate -ne $false) {
  throw "30A.3 simulation/presentation authority contract changed"
}
if ($Authority.sealed_cache_items_are_not_ground_loot -ne $true -or $Authority.single_holder_item_invariant -ne $true -or $Authority.relic_identity_is_canonical -ne $true) {
  throw "30A.3 cache/item/relic authority contract changed"
}
if ($Authority.resource_survival_owned_by -ne "30A.4") {
  throw "30A.3 crossed the 30A.4 resource/survival scope boundary"
}

Write-Host "[30A.3] Deterministic loot/cache/relic proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) population=$($P.population_count) strata=$($P.configured_stratum_count) caches=$($P.cache_count) relics=$($P.relic_blueprint_count)"
Write-Host "checkpointDigest=$($P.alpha_checkpoint_digest) checkpointEvents=$($P.alpha_checkpoint_event_count) checkpointStratumIndex=$($P.alpha_checkpoint_stratum_index)"
Write-Host "cacheStates=depleted:$($Statuses.depleted) opened:$($Statuses.opened) sealed:$($Statuses.sealed)"
Write-Host "materialized=$($P.final_materialized_item_count) owned=$($P.final_owned_item_count) ownedRelics=$($P.final_owned_relic_count)"
Write-Host "completed=$($P.completed_snapshot_digest)"

Write-Host "[30A.3] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30A.3] PASS"
Write-Host "Proof: $Proof"
