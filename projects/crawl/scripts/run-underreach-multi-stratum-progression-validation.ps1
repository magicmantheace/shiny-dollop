$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-multi-stratum-progression-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30a2"
$Proof = Join-Path $Out "multi-stratum-progression-proof.json"
$Repro = Join-Path $Out "multi-stratum-progression-proof-repro.json"
$Seed = "underreach-30a2-multi-stratum-progression-proof"

Write-Host "[30A.2] Accepted 30A.1 regression + focused multi-Stratum progression tests"
& $Python -m pytest -q tests/test_underreach_30a1_descent_run_state.py tests/test_underreach_30a2_multi_stratum_progression.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30A.2] Generating canonical four-Stratum progression proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8 --strata 4
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.multi-stratum-progression-proof.v1") {
  throw "30A.2 proof protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30A.2 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30A.2 deterministic Descent identity mismatch"
}
if ($P.authoritative -ne $true -or $P.presentation_feedback_allowed -ne $false) {
  throw "30A.2 authority boundary changed"
}
if ([int]$P.population_count -ne 8) {
  throw "30A.2 proof population count changed"
}
if ([int]$P.configured_stratum_count -ne 4 -or [int]$P.completed_stratum_count -ne 4) {
  throw "30A.2 did not realize and complete exactly four Strata"
}
if ([int]$P.transition_count -ne 3) {
  throw "30A.2 four-Stratum proof must contain exactly three transitions"
}
if ($P.transition_pairs.Count -ne 3) {
  throw "30A.2 transition pair proof is incomplete"
}
if ([int]$P.transition_pairs[0][0] -ne 1 -or [int]$P.transition_pairs[0][1] -ne 2) {
  throw "30A.2 transition sequence changed at index 0"
}
if ([int]$P.transition_pairs[1][0] -ne 2 -or [int]$P.transition_pairs[1][1] -ne 3) {
  throw "30A.2 transition sequence changed at index 1"
}
if ([int]$P.transition_pairs[2][0] -ne 3 -or [int]$P.transition_pairs[2][1] -ne 4) {
  throw "30A.2 transition sequence changed at index 2"
}
if ($P.transition_digests.Count -ne 3 -or $P.transition_ledger_event_ids.Count -ne 3) {
  throw "30A.2 transition digest/Ledger proof is incomplete"
}
if ([int]$P.survivor_count -ne 7 -or [int]$P.final_surviving_descender_count -ne 7) {
  throw "30A.2 survivor-selective progression proof changed"
}
if ([int]$P.final_eliminated_descender_count -ne 1 -or [int]$P.eliminated_descender_stratum_number -ne 1) {
  throw "30A.2 eliminated Descender did not remain behind on Stratum 1"
}
if ([int]$P.alpha_checkpoint_stratum_index -ne 1) {
  throw "30A.2 checkpoint did not restore after the first transition on Stratum index 1"
}
if ([int]$P.alpha_checkpoint_event_count -lt 10) {
  throw "30A.2 durable checkpoint did not bind a meaningful post-transition Ledger prefix"
}
if ($P.portable_restored_fingerprint -ne $P.alpha_checkpoint_restored_fingerprint) {
  throw "30A.2 portable/checkpoint restores disagree at the post-transition state"
}
if ($P.final_status -ne "completed" -or [int]$P.final_current_stratum_index -ne 3) {
  throw "30A.2 did not finish on the configured final Stratum"
}
if (-not $P.planned_snapshot_digest -or -not $P.active_snapshot_digest -or -not $P.final_stratum_active_snapshot_digest -or -not $P.completed_snapshot_digest) {
  throw "30A.2 lifecycle snapshot proof is incomplete"
}
if ($P.transition_snapshot_digests.Count -ne 3) {
  throw "30A.2 transition snapshot proof is incomplete"
}
$Authority = $P.authority_contract
if ($Authority.simulation_decides_truth -ne $true -or $Authority.unreal_can_mutate -ne $false -or $Authority.presentation_can_mutate -ne $false) {
  throw "30A.2 simulation/presentation authority contract changed"
}
if ($Authority.progression_is_sequential -ne $true -or $Authority.survivors_only_advance -ne $true) {
  throw "30A.2 sequential survivor progression contract changed"
}
if ($Authority.loot_owned_by -ne "30A.3") {
  throw "30A.2 crossed the 30A.3 loot scope boundary"
}

Write-Host "[30A.2] Deterministic multi-Stratum progression proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) population=$($P.population_count) strata=$($P.configured_stratum_count) transitions=$($P.transition_count)"
Write-Host "survivors=$($P.survivor_count) eliminated=$($P.final_eliminated_descender_count) finalStatus=$($P.final_status)"
Write-Host "checkpointDigest=$($P.alpha_checkpoint_digest) checkpointEvents=$($P.alpha_checkpoint_event_count) checkpointStratumIndex=$($P.alpha_checkpoint_stratum_index)"
Write-Host "transitionHistory=$($P.transition_history_digest)"
Write-Host "completed=$($P.completed_snapshot_digest)"

Write-Host "[30A.2] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30A.2] PASS"
Write-Host "Proof: $Proof"
