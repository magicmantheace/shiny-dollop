$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-ai-brain-foundation-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30b1"
$Proof = Join-Path $Out "ai-brain-foundation-proof.json"
$Repro = Join-Path $Out "ai-brain-foundation-proof-repro.json"
$Seed = "underreach-30b1-ai-brain-foundation-proof"

Write-Host "[30B.1] Accepted 30A.1-30A.5 regressions + focused AI brain foundation tests"
& $Python -m pytest -q `
  tests/test_underreach_30a1_descent_run_state.py `
  tests/test_underreach_30a2_multi_stratum_progression.py `
  tests/test_underreach_30a3_loot_cache_relic.py `
  tests/test_underreach_30a4_resources_survival.py `
  tests/test_underreach_30a5_full_autonomous_descent.py `
  tests/test_underreach_30b1_ai_brain_foundation.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30B.1] Generating read-only deterministic brain proposal proof twice"
& $Python $Generator --output $Proof --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed --count 8 --strata 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.ai-brain-foundation-proof.v1") {
  throw "30B.1 proof protocol changed"
}
if ($P.digest -ne $Q.digest) {
  throw "30B.1 proof reproducibility digest mismatch"
}
if ($P.descent_id -ne $Q.descent_id) {
  throw "30B.1 deterministic Descent identity mismatch"
}
if ($P.authoritative -ne $false -or $P.simulation_remains_authoritative -ne $true) {
  throw "30B.1 brain/simulation authority boundary changed"
}
if ($P.presentation_feedback_allowed -ne $false) {
  throw "30B.1 presentation feedback boundary changed"
}
if ([int]$P.population_count -ne 8 -or [int]$P.configured_stratum_count -ne 3) {
  throw "30B.1 acceptance population/Stratum shape changed"
}
if ([int]$P.initial_observation_count -ne 8 -or [int]$P.post_step_observation_count -lt 1) {
  throw "30B.1 did not produce proposals for active Descenders"
}
if ($P.initial_bundle_digest -eq $P.post_step_bundle_digest) {
  throw "30B.1 proposals did not respond to authoritative state change"
}
if ($P.provider_id -ne "deterministic-reference-v1") {
  throw "30B.1 reference provider identity changed"
}
if ($P.canonical_state_unchanged_by_proposals -ne $true) {
  throw "30B.1 proposal generation mutated canonical state"
}
if ($P.ledger_unchanged_by_proposals -ne $true) {
  throw "30B.1 proposal generation mutated canonical Ledger"
}
if ($P.fingerprint_unchanged_by_proposals -ne $true) {
  throw "30B.1 proposal generation changed canonical fingerprint"
}
if ($P.checkpoint_restored_bundle_exact -ne $true -or -not $P.checkpoint_digest -or [int]$P.checkpoint_event_count -lt 1) {
  throw "30B.1 checkpoint proposal reproducibility proof is incomplete"
}
if (-not $P.post_step_actions -or $P.post_step_actions.Count -lt 1) {
  throw "30B.1 proof did not produce bounded actions"
}

$Authority = $P.authority_contract
if ($Authority.brain_can_observe -ne $true -or $Authority.brain_can_propose -ne $true) {
  throw "30B.1 brain observation/proposal capability changed"
}
if ($Authority.brain_can_execute -ne $false -or $Authority.brain_can_mutate_descent -ne $false) {
  throw "30B.1 brain crossed execution authority boundary"
}
if ($Authority.brain_can_append_gameplay_ledger -ne $false) {
  throw "30B.1 advisory proposals became gameplay Ledger truth"
}
if ($Authority.simulation_validation_required_before_execution -ne $true) {
  throw "30B.1 removed deterministic execution gate"
}
if ($Authority.unreal_can_mutate -ne $false -or $Authority.presentation_can_mutate -ne $false) {
  throw "30B.1 Unreal/presentation authority boundary changed"
}

Write-Host "[30B.1] Deterministic AI brain foundation proof PASS"
Write-Host "digest=$($P.digest) descent=$($P.descent_id) population=$($P.population_count)"
Write-Host "initialBundle=$($P.initial_bundle_digest) postStepBundle=$($P.post_step_bundle_digest)"
Write-Host "provider=$($P.provider_id) actions=$($P.post_step_actions -join ',')"
Write-Host "checkpointDigest=$($P.checkpoint_digest) checkpointEvents=$($P.checkpoint_event_count)"

Write-Host "[30B.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30B.1] PASS"
Write-Host "Proof: $Proof"
