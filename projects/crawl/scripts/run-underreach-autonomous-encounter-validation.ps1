param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generator = Join-Path $RepoRoot "scripts\generate-underreach-autonomous-encounter-proof.py"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_autonomous_encounter_proof.py"
$OutputDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29c3"
$Canonical = Join-Path $OutputDir "autonomous-encounter-canonical.json"
$Repro = Join-Path $OutputDir "autonomous-encounter-canonical-repro.json"
$DebugPath = Join-Path $OutputDir "autonomous-encounter-unreal-debug.json"
$UnrealLog = Join-Path $OutputDir "unreal-autonomous-encounter-proof.log"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Generator, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29C.3 input missing: $Required" }
}

Write-Host "[29C.3] Focused deterministic autonomous encounter tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py tests/test_underreach_29b21_live_traversal.py tests/test_underreach_29b3_stratum_theme.py tests/test_underreach_29c1_monster_encounters.py tests/test_underreach_29c2_live_encounters.py tests/test_underreach_29c3_autonomous_encounters.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($Generated in @($Canonical, $Repro, $DebugPath, $UnrealLog)) {
    if (Test-Path $Generated) { Remove-Item -Force $Generated }
}

Write-Host "[29C.3] Generating canonical autonomous flow twice for reproducibility"
& $Python $Generator --output $Canonical --seed "underreach-29c3-autonomous-proof" --theme "ancient_stoneworks" --sectors 12 --descenders 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed "underreach-29c3-autonomous-proof" --theme "ancient_stoneworks" --sectors 12 --descenders 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$CanonicalJson = Get-Content -Raw $Canonical | ConvertFrom-Json
$ReproJson = Get-Content -Raw $Repro | ConvertFrom-Json
if ($CanonicalJson.protocol -ne "underreach.autonomous-encounter-flow.v1") { throw "Unexpected 29C.3 canonical protocol: $($CanonicalJson.protocol)" }
if ($CanonicalJson.authoritative -ne $true) { throw "29C.3 canonical flow is not authoritative" }
if ($CanonicalJson.presentation.authoritative -ne $false) { throw "29C.3 presentation became authoritative" }
if ($CanonicalJson.digest -ne $ReproJson.digest) { throw "29C.3 identical input did not reproduce proof digest" }
if ($CanonicalJson.canonical_digest -ne $ReproJson.canonical_digest) { throw "29C.3 identical input did not reproduce canonical digest" }
if ($CanonicalJson.canonical_truth.frames.Count -lt 2) { throw "29C.3 autonomous flow did not span multiple ticks" }
if ($CanonicalJson.canonical_truth.frames.Count -gt 120) { throw "29C.3 autonomous flow exceeded bounded tick budget" }
$EmptyFocus = @($CanonicalJson.canonical_truth.frames | Where-Object { $null -eq $_.feed_focus_actor_id }).Count
if ($EmptyFocus -ne 0) { throw "29C.3 canonical Feed schedule contains empty focus windows" }
$EventTypes = @($CanonicalJson.canonical_truth.ledger_events | ForEach-Object { $_.event_type })
foreach ($RequiredEvent in @("UNDERREACH_DESCENDER_ENTERED_ENCOUNTER", "UNDERREACH_MONSTER_TARGET_ACQUIRED", "UNDERREACH_MONSTER_MOVED", "UNDERREACH_MONSTER_ATTACKED", "UNDERREACH_DESCENDER_ATTACKED_MONSTER", "UNDERREACH_LIVE_ENCOUNTER_ENDED")) {
    if ($EventTypes -notcontains $RequiredEvent) { throw "29C.3 Ledger missing required event $RequiredEvent" }
}
$CanonicalHashBefore = (Get-FileHash -Algorithm SHA256 $Canonical).Hash.ToLowerInvariant()

Write-Host "[29C.3] Canonical autonomous flow PASS"
Write-Host "canonicalDigest=$($CanonicalJson.canonical_digest) proofDigest=$($CanonicalJson.digest) outcome=$($CanonicalJson.canonical_truth.outcome)"
Write-Host "frames=$($CanonicalJson.canonical_truth.frames.Count) ledgerEvents=$($CanonicalJson.canonical_truth.ledger_events.Count)"

$StartedUtc = [DateTime]::UtcNow
Write-Host "[29C.3] Unreal autonomous encounter + Feed consumer proof"
Write-Host "[29C.3] NullRHI enabled so remote validation does not require a desktop/D3D viewport"
Write-Host "[29C.3] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE

if (-not (Test-Path $DebugPath)) {
    Write-Host "[29C.3] FAIL: Unreal proof produced no diagnostics. Unreal exit code: $UnrealExit"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29C3" -Context 1,3 | Select-Object -Last 40
    if ($Matches) { $Matches | ForEach-Object { $_.ToString() } | Write-Host }
    else { Get-Content $UnrealLog -Tail 120 | Write-Host }
    throw "29C.3 Unreal proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $DebugPath).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "29C.3 Unreal diagnostics are stale. Unreal exit code: $UnrealExit"
}

$Debug = Get-Content -Raw $DebugPath | ConvertFrom-Json
$CanonicalHashAfter = (Get-FileHash -Algorithm SHA256 $Canonical).Hash.ToLowerInvariant()
if ($Debug.protocol -ne "underreach.autonomous-encounter-unreal-debug.v1") { throw "Unexpected 29C.3 Unreal protocol: $($Debug.protocol)" }
if ($Debug.authoritative -ne $false) { throw "29C.3 Unreal presentation became authoritative" }
if (-not $Debug.validation.all_pass) { throw "29C.3 Unreal validation flags failed" }
if ($Debug.canonical_digest -ne $CanonicalJson.canonical_digest) { throw "29C.3 Unreal consumed wrong canonical digest" }
if ($CanonicalHashBefore -ne $CanonicalHashAfter) { throw "29C.3 Unreal modified canonical encounter artifact" }
if ($Debug.canonical_file_sha256_before -ne $CanonicalHashBefore -or $Debug.canonical_file_sha256_after -ne $CanonicalHashBefore) { throw "29C.3 Unreal canonical file hash evidence inconsistent" }
if ([int]$Debug.replayed_frame_count -ne [int]$CanonicalJson.canonical_truth.frames.Count) { throw "29C.3 Unreal did not replay every canonical frame" }
if ([int]$Debug.empty_feed_focus_windows -ne 0 -or [int]$Debug.stale_feed_focus_windows -ne 0) { throw "29C.3 Feed had empty/stale focus windows" }
if ([double]$Debug.max_actor_location_error_cm -gt 0.01) { throw "29C.3 Unreal actor motion diverged from canonical frames" }
if ([double]$Debug.max_feed_camera_focus_distance_error_cm -gt 0.01) { throw "29C.3 Feed camera did not track canonical focus" }
if ([int]$Debug.attack_frame_count -lt 1 -or [int]$Debug.target_acquisition_frame_count -lt 1) { throw "29C.3 Unreal proof did not present live encounter action" }

Write-Host "[29C.3] Unreal autonomous encounter proof PASS"
Write-Host "outcome=$($Debug.outcome) frames=$($Debug.frame_count) actors=$($Debug.actor_count) attacks=$($Debug.attack_frame_count) targetFrames=$($Debug.target_acquisition_frame_count)"
Write-Host "emptyFeed=$($Debug.empty_feed_focus_windows) staleFeed=$($Debug.stale_feed_focus_windows) maxActorErrorCm=$($Debug.max_actor_location_error_cm)"
if ($UnrealExit -ne 0) {
    Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status."
}

Write-Host "[29C.3] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29C.3] PASS"
Write-Host "Canonical: $Canonical"
Write-Host "Diagnostics: $DebugPath"
Write-Host "Unreal log: $UnrealLog"
