$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-highlight-story-arc-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_3"
$Proof = Join-Path $Out "highlight-story-arc-proof.json"
$Repro = Join-Path $Out "highlight-story-arc-proof-repro.json"
$Seed = "underreach-30-5-3-highlight-proof"

Write-Host "[30.5.3] Accepted 30A.1-30.5.2 regressions + focused highlight/story-arc tests"
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
  tests/test_underreach_30_5_3_highlight_story_arc_detection.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.3] Running deterministic file-backed highlight/story-arc proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.highlight-story-arc-proof.v1") { throw "30.5.3 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.highlight-story-arc.v1") { throw "30.5.3 slice protocol changed" }
if ($P.implementation_version -ne "30.5.3") { throw "30.5.3 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.3 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.3 media snapshot reproducibility mismatch" }

$T = $P.tier_boundaries
if ($T."49" -ne "archive_only") { throw "30.5.3 0-49 tier changed" }
if ($T."50" -ne "chronicle" -or $T."69" -ne "chronicle") { throw "30.5.3 50-69 tier changed" }
if ($T."70" -ne "motion_story" -or $T."79" -ne "motion_story") { throw "30.5.3 70-79 tier changed" }
if ($T."80" -ne "enhanced_stills" -or $T."89" -ne "enhanced_stills") { throw "30.5.3 80-89 tier changed" }
if ($T."90" -ne "local_animation" -or $T."94" -ne "local_animation") { throw "30.5.3 90-94 tier changed" }
if ($T."95" -ne "cinematic" -or $T."100" -ne "cinematic") { throw "30.5.3 95-100 tier changed" }

$H = $P.high_signal
if ($H.selected -ne $true -or -not $H.highlight_id) { throw "30.5.3 high-signal event was not persisted as highlight" }
if ([int]$H.total_score -lt 80) { throw "30.5.3 high-signal score unexpectedly low" }
if ([int]$H.danger -lt 18) { throw "30.5.3 danger scoring lost near-death evidence" }
if ([int]$H.rarity -ne 15) { throw "30.5.3 Relic rarity score changed" }
if ([int]$H.social_stakes -ne 20) { throw "30.5.3 betrayal social-stakes score changed" }
if ([int]$H.outcome_reversal -ne 10) { throw "30.5.3 comeback/reversal score changed" }
if ([int]$H.continuity -ne 15) { throw "30.5.3 reinforced-memory continuity score changed" }
if ([int]$H.visual_potential -lt 4) { throw "30.5.3 visual-potential evidence disappeared" }
if ($H.tier -ne "enhanced_stills") { throw "30.5.3 high-signal output tier changed" }
if ($H.repeat_equal -ne $true -or $H.reopen_repeat_equal -ne $true) { throw "30.5.3 highlight idempotency/restart equality failed" }

$L = $P.low_signal
if ($L.selected -ne $false -or $L.highlight_id) { throw "30.5.3 low-signal event incorrectly became a highlight" }
if ([int]$L.total_score -ge 50 -or $L.tier -ne "archive_only") { throw "30.5.3 archive-only threshold changed" }

$S = $P.story_arcs
if ([int]$S.count -lt 5) { throw "30.5.3 story-arc coverage is too small" }
if ([int]$S.survival_arc_count -lt 1 -or $S.survival_closed -ne $true) { throw "30.5.3 terminal survival arc did not close" }
if ([int]$S.social_conflict_arc_count -lt 1) { throw "30.5.3 social-conflict arc missing" }
if ([int]$S.loot_progression_arc_count -lt 1) { throw "30.5.3 loot/progression arc missing" }
if ($S.all_have_provenance -ne $true) { throw "30.5.3 story arc lost canonical/media provenance" }

$M = $P.media
if ([int]$M.highlight_count -ne 1) { throw "30.5.3 persisted highlight count changed" }
if ([int]$M.story_arc_count -lt 5) { throw "30.5.3 persisted story-arc count changed" }
if ($M.snapshot_equal_after_reopen -ne $true -or $M.snapshot_equal_after_repeat -ne $true) { throw "30.5.3 SQLite restart/idempotency snapshot changed" }
if ([int]$M.media_job_count -ne 0) { throw "30.5.3 unexpectedly enqueued generation jobs" }

$C = $P.canonical
if ($C.state_unchanged -ne $true -or $C.fingerprint_unchanged -ne $true) { throw "30.5.3 changed canonical state" }
if ($C.history_unchanged -ne $true -or $C.ledger_rows_unchanged -ne $true) { throw "30.5.3 changed canonical Ledger history" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.3 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.3 presentation gained simulation authority" }
if ($A.llm_decision_used -ne $false) { throw "30.5.3 introduced LLM highlight decisions" }
if ($A.unreal_dependency -ne $false -or $A.provider_invocation_used -ne $false) { throw "30.5.3 introduced Unreal/provider invocation" }
if ($A.highlight_detection_is_deterministic_python -ne $true) { throw "30.5.3 deterministic detector contract changed" }
if ($A.highlight_detection_enqueues_generation_jobs -ne $false) { throw "30.5.3 absorbed downstream generation scheduling" }

Write-Host "[30.5.3] Deterministic highlight/story-arc proof PASS"
Write-Host "digest=$($P.digest) highScore=$($H.total_score) tier=$($H.tier) highlights=$($M.highlight_count) arcs=$($M.story_arc_count)"
Write-Host "lowScore=$($L.total_score) survivalClosed=$($S.survival_closed) jobs=$($M.media_job_count)"

Write-Host "[30.5.3] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.3] PASS"
Write-Host "Proof: $Proof"