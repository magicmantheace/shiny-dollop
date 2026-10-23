$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-delver-chronicle-profile-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_4"
$Proof = Join-Path $Out "delver-chronicle-profile-proof.json"
$Repro = Join-Path $Out "delver-chronicle-profile-proof-repro.json"
$Seed = "underreach-30-5-4-chronicle-proof"

Write-Host "[30.5.4] Accepted 30A.1-30.5.3 regressions + focused Chronicle/profile tests"
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
  tests/test_underreach_30_5_2_media_db_durable_queue_provider_router.py `
  tests/test_underreach_30_5_3_highlight_story_arc_detection.py `
  tests/test_underreach_30_5_4_delver_chronicle_profile_system.py `
  tests/test_underreach_30_5_4_terminal_archive_only.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.4] Running deterministic file-backed Chronicle/profile proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.delver-chronicle-profile-proof.v1") { throw "30.5.4 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.delver-chronicle-profile.v1") { throw "30.5.4 slice protocol changed" }
if ($P.implementation_version -ne "30.5.4") { throw "30.5.4 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.4 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.4 media snapshot reproducibility mismatch" }
if ($P.media.profile_digest -ne $Q.media.profile_digest) { throw "30.5.4 profile reproducibility mismatch" }
if ($P.media.chapter_digest -ne $Q.media.chapter_digest) { throw "30.5.4 chapter reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.4 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.4 presentation gained simulation authority" }
if ($A.generated_prose_used -ne $false) { throw "30.5.4 generated prose before verification slice" }
if ($A.claim_verification_required_before_prose -ne $true) { throw "30.5.4 claim-verification boundary changed" }
if ($A.unreal_dependency -ne $false -or $A.provider_invocation_used -ne $false) { throw "30.5.4 introduced Unreal/provider invocation" }

$C = $P.canonical
if ($C.state_unchanged -ne $true -or $C.fingerprint_unchanged -ne $true) { throw "30.5.4 changed canonical state" }
if ($C.history_unchanged -ne $true -or $C.ledger_rows_unchanged -ne $true) { throw "30.5.4 changed canonical Ledger history" }

$H = $P.highlight_input
if ($H.high_selected -ne $true -or -not $H.high_highlight_id) { throw "30.5.4 high-signal source lacks accepted highlight" }
if ($H.quiet_all_archive_only -ne $true -or $H.quiet_all_have_arcs -ne $true) { throw "30.5.4 quiet-history proof inputs changed" }
if ($H.death_selected -ne $false) { throw "30.5.4 proof must preserve archive-only terminal death coverage" }

$R = $P.profiles
if ([int]$R.count -ne 3) { throw "30.5.4 profile count changed" }
if ($R.delver0_status -ne "DEAD" -or $R.delver0_closed -ne $true) { throw "30.5.4 terminal profile did not close" }
if (-not $R.delver0_party_id) { throw "30.5.4 current party context missing" }
if (@($R.delver0_alliance_ids).Count -lt 1) { throw "30.5.4 alliance context missing" }
if (-not $R.alliance_id -or $R.delver0_alliance_ids -notcontains $R.alliance_id) { throw "30.5.4 accepted alliance identity not surfaced" }
if ($R.delver1_status -ne "ACTIVE" -or $R.delver1_closed -ne $false) { throw "30.5.4 nonterminal highlighted Delver profile changed" }
if ($R.delver2_status -ne "ACTIVE" -or $R.delver2_closed -ne $false) { throw "30.5.4 quiet-history Delver profile changed" }
if ([int]$R.delver2_quiet_pending -ne 0) { throw "30.5.4 quiet-history batch did not clear after recap" }

$Ch = $P.chapters
if ([int]$Ch.count -ne 4) { throw "30.5.4 Chronicle chapter count changed" }
if ([int]$Ch.highlight_count -ne 2) { throw "30.5.4 highlight chapter fan-out changed" }
if ([int]$Ch.quiet_recap_count -ne 1) { throw "30.5.4 quiet recap chapter missing" }
if ([int]$Ch.terminal_count -ne 1) { throw "30.5.4 terminal chapter missing" }
if ($Ch.all_structured_only -ne $true -or $Ch.all_require_claim_verification -ne $true) { throw "30.5.4 structured/pre-verification chapter boundary changed" }
if ($Ch.none_generated_prose -ne $true) { throw "30.5.4 generated prose appeared in structured Chronicle" }
if ($Ch.all_have_fact_provenance -ne $true) { throw "30.5.4 chapter fact/event provenance missing" }
if ($Ch.terminal_is_death -ne $true) { throw "30.5.4 terminal death title/status changed" }
if ([int]$Ch.quiet_source_envelope_count -ne 3) { throw "30.5.4 quiet recap batch size changed" }

$M = $P.media
if ($M.snapshot_equal_after_reopen -ne $true) { throw "30.5.4 media snapshot changed after SQLite reopen" }
if ($M.snapshot_equal_after_repeat -ne $true) { throw "30.5.4 duplicate reprocessing changed media snapshot" }
if ([int]$M.media_job_count -ne 0) { throw "30.5.4 unexpectedly enqueued generation jobs" }
if ([int]$M.repeat_terminal_profile_count -ne 1) { throw "30.5.4 terminal duplicate processing result changed" }

Write-Host "[30.5.4] Delver Chronicle/profile proof PASS"
Write-Host "digest=$($P.digest) profiles=$($R.count) chapters=$($Ch.count) closed=$($R.delver0_closed)"
Write-Host "highlight=$($Ch.highlight_count) quiet=$($Ch.quiet_recap_count) terminal=$($Ch.terminal_count) jobs=$($M.media_job_count)"

Write-Host "[30.5.4] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.4] PASS"
Write-Host "Proof: $Proof"
