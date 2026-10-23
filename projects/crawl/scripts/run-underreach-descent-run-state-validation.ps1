$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-descent-run-state-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30a1"
$Proof = Join-Path $Out "descent-run-state-proof.json"
$Repro = Join-Path $Out "descent-run-state-proof-repro.json"
$Seed = "underreach-30a1-descent-run-state-proof"

Write-Host "[30A.1] Focused deterministic Descent run-state tests"
& $Python -m pytest -q tests/test_underreach_30a1_descent_run_state.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30A.1] Generating canonical run-state proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.descent-run-state-proof.v1") {
  throw "30A.1 proof protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30A.1 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30A.1 deterministic Descent identity mismatch"
}
if ($P.authoritative -ne $true -or $P.presentation_feedback_allowed -ne $false) {
  throw "30A.1 authority boundary changed"
}
if ([int]$P.population_count -ne 8) {
  throw "30A.1 proof population count changed"
}
if ([int]$P.initialized_stratum_count -ne 1 -or [int]$P.current_stratum_index -ne 0) {
  throw "30A.1 must remain scoped to the initial Stratum"
}
if ($P.multi_stratum_progression_enabled -ne $false) {
  throw "30A.1 illegally enabled multi-Stratum progression"
}
if ($P.final_status -ne "completed") {
  throw "30A.1 did not prove planned -> active -> completed lifecycle"
}
if (-not $P.planned_snapshot_digest -or -not $P.active_snapshot_digest -or -not $P.moved_snapshot_digest -or -not $P.completed_snapshot_digest) {
  throw "30A.1 lifecycle snapshot proof is incomplete"
}
if ($P.portable_restored_fingerprint -ne $P.alpha_checkpoint_restored_fingerprint) {
  throw "30A.1 portable/checkpoint restores disagree at checkpoint state"
}
if ([int]$P.alpha_checkpoint_event_count -lt 4) {
  throw "30A.1 durable checkpoint did not bind a meaningful Ledger prefix"
}
$Authority = $P.authority_contract
if ($Authority.simulation_decides_truth -ne $true -or $Authority.unreal_can_mutate -ne $false -or $Authority.presentation_can_mutate -ne $false) {
  throw "30A.1 simulation/presentation authority contract changed"
}
if ($Authority.multi_stratum_advancement_owned_by -ne "30A.2") {
  throw "30A.1 crossed the 30A.2 scope boundary"
}

Write-Host "[30A.1] Deterministic run-state proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) population=$($P.population_count) finalEvents=$($P.final_event_count)"
Write-Host "checkpointDigest=$($P.alpha_checkpoint_digest) checkpointEvents=$($P.alpha_checkpoint_event_count)"
Write-Host "planned=$($P.planned_snapshot_digest)"
Write-Host "active=$($P.active_snapshot_digest)"
Write-Host "moved=$($P.moved_snapshot_digest)"
Write-Host "completed=$($P.completed_snapshot_digest)"

Write-Host "[30A.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30A.1] PASS"
Write-Host "Proof: $Proof"
