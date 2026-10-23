$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Generator = Join-Path $RepoRoot "scripts\generate-underreach-narrative-claim-verification-proof.py"
$Out = Join-Path $RepoRoot "validation\underreach-30_5_5"
$Proof = Join-Path $Out "narrative-claim-verification-proof.json"
$Repro = Join-Path $Out "narrative-claim-verification-proof-repro.json"
$Seed = "underreach-30-5-5-narrative-proof"

Write-Host "[30.5.5] Accepted 30A.1-30.5.4 regressions + focused narrative verification tests"
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
  tests/test_underreach_30_5_4_terminal_archive_only.py `
  tests/test_underreach_30_5_5_narrative_claim_manifest_fact_verification.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "[30.5.5] Running deterministic file-backed narrative claim verification proof twice"
& $Python $Generator --output $Proof --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$P = Get-Content -Raw $Proof | ConvertFrom-Json
$Q = Get-Content -Raw $Repro | ConvertFrom-Json

if ($P.protocol -ne "underreach.narrative-claim-verification-proof.v1") { throw "30.5.5 proof protocol changed" }
if ($P.slice_protocol -ne "underreach.narrative-claim-verification.v1") { throw "30.5.5 slice protocol changed" }
if ($P.implementation_version -ne "30.5.5") { throw "30.5.5 implementation version changed" }
if ($P.phase -ne "30.5") { throw "30.5 phase must remain a string" }
if ($P.digest -ne $Q.digest) { throw "30.5.5 proof reproducibility digest mismatch" }
if ($P.media.snapshot_digest -ne $Q.media.snapshot_digest) { throw "30.5.5 snapshot reproducibility mismatch" }
if ($P.media.draft_digest -ne $Q.media.draft_digest) { throw "30.5.5 draft reproducibility mismatch" }
if ($P.media.manifest_digest -ne $Q.media.manifest_digest) { throw "30.5.5 manifest reproducibility mismatch" }
if ($P.media.verification_digest -ne $Q.media.verification_digest) { throw "30.5.5 verification reproducibility mismatch" }

$A = $P.authority_contract
if ($A.authoritative -ne $false -or $A.canonical_owner -ne "deterministic_simulation") { throw "30.5.5 authority boundary changed" }
if ($A.presentation_can_mutate_simulation -ne $false) { throw "30.5.5 presentation gained simulation authority" }
if ($A.writer_self_certification_trusted -ne $false) { throw "30.5.5 began trusting writer self-certification" }
if ($A.auxiliary_model_can_override_deterministic_checks -ne $false) { throw "30.5.5 auxiliary model gained deterministic override authority" }
if ($A.local_model_required -ne $false) { throw "30.5.5 made local model mandatory for deterministic verification" }
if ($A.cloud_api_required -ne $false -or $A.paid_provider_required -ne $false) { throw "30.5.5 added required cloud/paid dependency" }
if ($A.provider_invocation_used -ne $false) { throw "30.5.5 directly invoked a provider" }

$C = $P.canonical
if ($C.state_unchanged -ne $true -or $C.fingerprint_unchanged -ne $true) { throw "30.5.5 changed canonical state" }
if ($C.history_unchanged -ne $true -or $C.ledger_rows_unchanged -ne $true) { throw "30.5.5 changed canonical Ledger history" }

$R = $P.review_ready
if ($R.status -ne "review_ready" -or $R.review_ready -ne $true) { throw "30.5.5 exact allowed claims did not become review-ready" }
if ($R.all_sentences_covered -ne $true) { throw "30.5.5 valid draft sentence coverage failed" }
if ([int]$R.contradictions -ne 0 -or [int]$R.unsupported -ne 0) { throw "30.5.5 valid draft produced false verification failures" }
$claimStatuses = @($R.claim_statuses)
if ($claimStatuses -notcontains "verified" -or $claimStatuses -notcontains "style_safe") { throw "30.5.5 valid factual/style claim statuses changed" }
if ($R.writer_provider_local -ne $true -or $R.writer_provider_paid -ne $false) { throw "30.5.5 local writer provenance changed" }
if ($R.repeat_equal -ne $true) { throw "30.5.5 duplicate verification was not idempotent" }

$W = $P.wrong_stratum
if ($W.status -ne "rejected" -or $W.review_ready -ne $false) { throw "30.5.5 wrong Stratum was not rejected" }
if ([int]$W.contradictions -ne 1) { throw "30.5.5 wrong Stratum contradiction count changed" }
if ($W.reason_codes -notcontains "deterministic_contradiction") { throw "30.5.5 deterministic contradiction reason missing" }
if ($W.auxiliary_used -ne $true) { throw "30.5.5 auxiliary non-override proof disappeared" }
if ($W.auxiliary_override_allowed -ne $false) { throw "30.5.5 auxiliary assessment overrode deterministic contradiction" }

$S = $P.style_guard
if ($S.status -ne "rejected" -or $S.review_ready -ne $false) { throw "30.5.5 factual language disguised as style was not rejected" }
if ([int]$S.unsupported -ne 1) { throw "30.5.5 style-guard rejection count changed" }
$styleJson = $S.claim_reason_codes | ConvertTo-Json -Compress -Depth 8
if ($styleJson -notmatch "stylistic_sentence_contains_factual_signal") { throw "30.5.5 style factual-signal reason missing" }

$N = $P.ambiguous
if ($N.status -ne "needs_review" -or $N.review_ready -ne $false) { throw "30.5.5 auxiliary ambiguity did not downgrade to needs-review" }
if ([int]$N.contradictions -ne 0) { throw "30.5.5 valid ambiguous claim became deterministic contradiction" }
if ($N.auxiliary_used -ne $true) { throw "30.5.5 auxiliary ambiguity provenance missing" }
if ($N.reason_codes -notcontains "auxiliary_ambiguous_signal") { throw "30.5.5 ambiguity reason missing" }

$M = $P.media
if ([int]$M.draft_count -ne 4 -or [int]$M.manifest_count -ne 4 -or [int]$M.verification_count -ne 4) { throw "30.5.5 durable narrative record counts changed" }
if ($M.snapshot_equal_after_reopen -ne $true) { throw "30.5.5 media snapshot changed after SQLite reopen" }
if ($M.snapshot_equal_after_repeat -ne $true) { throw "30.5.5 duplicate verification changed media snapshot" }
if ([int]$M.media_job_count -ne 0) { throw "30.5.5 unexpectedly enqueued generation jobs" }
if ([int]$M.provider_execution_count -ne 0) { throw "30.5.5 unexpectedly executed/recorded provider execution" }

Write-Host "[30.5.5] Narrative claim manifest / fact verification proof PASS"
Write-Host "digest=$($P.digest) ready=$($R.status) wrong=$($W.status) ambiguous=$($N.status)"
Write-Host "drafts=$($M.draft_count) manifests=$($M.manifest_count) verifications=$($M.verification_count) jobs=$($M.media_job_count)"

Write-Host "[30.5.5] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[30.5.5] PASS"
Write-Host "Proof: $Proof"
