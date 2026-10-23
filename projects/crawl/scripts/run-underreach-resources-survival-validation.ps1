$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-resources-survival-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30a4"
$Proof = Join-Path $Out "resources-survival-proof.json"
$Repro = Join-Path $Out "resources-survival-proof-repro.json"
$Seed = "underreach-30a4-resources-survival-proof"

Write-Host "[30A.4] Accepted 30A.1-30A.3 regression + focused resources/survival tests"
& $Python -m pytest -q tests/test_underreach_30a1_descent_run_state.py tests/test_underreach_30a2_multi_stratum_progression.py tests/test_underreach_30a3_loot_cache_relic.py tests/test_underreach_30a4_resources_survival.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30A.4] Generating canonical four-Stratum resources/survival proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.resources-survival-proof.v1") {
  throw "30A.4 proof protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30A.4 deterministic proof digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30A.4 deterministic Descent identity mismatch"
}
if ($P.authoritative -ne $true -or $P.presentation_feedback_allowed -ne $false) {
  throw "30A.4 authority boundary changed"
}
if ([int]$P.population_count -ne 8 -or [int]$P.configured_stratum_count -ne 4) {
  throw "30A.4 proof population/Stratum count changed"
}
if ([int]$P.supply_cache_count -ne 4) {
  throw "30A.4 must bind one survival supply cache to each accepted loot cache"
}
if (-not $P.planned_snapshot_digest -or -not $P.active_snapshot_digest -or -not $P.pressure_snapshot_digest -or -not $P.second_pressure_snapshot_digest -or -not $P.completed_snapshot_digest) {
  throw "30A.4 lifecycle/resource snapshot proof is incomplete"
}
if ($P.transition_snapshot_digests.Count -ne 3) {
  throw "30A.4 four-Stratum proof must preserve survival state across three transitions"
}
$PressureCount = [int]$P.pressure_risk_band_counts.warning + [int]$P.pressure_risk_band_counts.critical
if ($PressureCount -lt 1) {
  throw "30A.4 initial pressure window did not create any survival pressure"
}
if ([int]$P.second_pressure_risk_band_counts.critical -lt 1) {
  throw "30A.4 second pressure window did not reach critical survival pressure"
}
if ([int]$P.final_health_pressure_count -lt 1) {
  throw "30A.4 critical deprivation did not apply canonical health pressure"
}
if ([double]$P.water_resource_after -le [double]$P.water_resource_before) {
  throw "30A.4 water supply did not replenish hydration"
}
if ([double]$P.ration_resource_after -le [double]$P.ration_resource_before) {
  throw "30A.4 ration supply did not replenish nutrition"
}
if ([double]$P.safe_recovery_stamina_after -le [double]$P.safe_recovery_stamina_before) {
  throw "30A.4 safe-area recovery did not restore canonical gameplay stamina"
}
if ([int]$P.alpha_checkpoint_stratum_index -ne 1) {
  throw "30A.4 checkpoint did not restore after Stratum 1 -> 2 transition"
}
if ([int]$P.alpha_checkpoint_event_count -lt 10) {
  throw "30A.4 checkpoint did not bind a meaningful canonical Ledger prefix"
}
if ($P.portable_restored_fingerprint -ne $P.alpha_checkpoint_restored_fingerprint) {
  throw "30A.4 portable/checkpoint restores disagree at the post-transition state"
}
if ([int]$P.revealed_supply_cache_count -ne 2 -or [int]$P.depleted_supply_cache_count -ne 1) {
  throw "30A.4 final survival supply cache state changed"
}
if ([int]$P.materialized_supply_count -ne 4 -or [int]$P.claimed_supply_count -ne 3 -or [int]$P.consumed_supply_count -ne 2) {
  throw "30A.4 supply materialization/claim/consumption proof changed"
}
if ($P.final_status -ne "completed" -or [int]$P.final_current_stratum_index -ne 3) {
  throw "30A.4 did not complete the four-Stratum Descent"
}
$RequiredEvents = @(
  "RESOURCES_SURVIVAL_INITIALIZED",
  "SURVIVAL_TIME_APPLIED",
  "SURVIVAL_SUPPLIES_REVEALED",
  "SURVIVAL_SUPPLY_ACQUIRED",
  "SURVIVAL_RESOURCE_CONSUMED",
  "SURVIVAL_SAFE_RECOVERY",
  "SURVIVAL_STRATUM_CARRIED_FORWARD"
)
foreach ($EventType in $RequiredEvents) {
  if ($P.event_types -notcontains $EventType) {
    throw "30A.4 missing canonical Ledger event type: $EventType"
  }
}
$Authority = $P.authority_contract
if ($Authority.simulation_decides_truth -ne $true -or $Authority.unreal_can_mutate -ne $false -or $Authority.presentation_can_mutate -ne $false) {
  throw "30A.4 simulation/presentation authority contract changed"
}
if ($Authority.hydration_nutrition_are_canonical -ne $true -or $Authority.stamina_reuses_existing_gameplay_state -ne $true) {
  throw "30A.4 survival resource/stamina authority contract changed"
}
if ($Authority.autonomous_survival_choices_owned_by -ne "30A.5") {
  throw "30A.4 crossed the 30A.5 autonomous Descent scope boundary"
}

Write-Host "[30A.4] Deterministic resources/survival proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) population=$($P.population_count) strata=$($P.configured_stratum_count) supplyCaches=$($P.supply_cache_count)"
Write-Host "pressure=stable:$($P.pressure_risk_band_counts.stable) warning:$($P.pressure_risk_band_counts.warning) critical:$($P.pressure_risk_band_counts.critical)"
Write-Host "secondPressure=stable:$($P.second_pressure_risk_band_counts.stable) warning:$($P.second_pressure_risk_band_counts.warning) critical:$($P.second_pressure_risk_band_counts.critical) healthPressure=$($P.final_health_pressure_count)"
Write-Host "supplies=revealed:$($P.revealed_supply_cache_count) depleted:$($P.depleted_supply_cache_count) materialized:$($P.materialized_supply_count) claimed:$($P.claimed_supply_count) consumed:$($P.consumed_supply_count)"
Write-Host "checkpointDigest=$($P.alpha_checkpoint_digest) checkpointEvents=$($P.alpha_checkpoint_event_count) checkpointStratumIndex=$($P.alpha_checkpoint_stratum_index)"
Write-Host "completed=$($P.completed_snapshot_digest)"

Write-Host "[30A.4] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30A.4] PASS"
Write-Host "Proof: $Proof"
