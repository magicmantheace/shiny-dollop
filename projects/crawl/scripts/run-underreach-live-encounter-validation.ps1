param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generator = Join-Path $RepoRoot "scripts\generate-underreach-live-encounter-proof.py"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_live_encounter_proof.py"
$OutputDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29c2"
$Canonical = Join-Path $OutputDir "live-encounter-canonical.json"
$Repro = Join-Path $OutputDir "live-encounter-canonical-repro.json"
$DebugPath = Join-Path $OutputDir "live-encounter-unreal-debug.json"
$UnrealLog = Join-Path $OutputDir "unreal-live-encounter-proof.log"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Generator, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29C.2 input missing: $Required" }
}

Write-Host "[29C.2] Focused deterministic live encounter tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py tests/test_underreach_29b21_live_traversal.py tests/test_underreach_29b3_stratum_theme.py tests/test_underreach_29c1_monster_encounters.py tests/test_underreach_29c2_live_encounters.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($Generated in @($Canonical, $Repro, $DebugPath, $UnrealLog)) {
    if (Test-Path $Generated) { Remove-Item -Force $Generated }
}

Write-Host "[29C.2] Generating canonical combat proof twice for reproducibility"
& $Python $Generator --output $Canonical --seed "underreach-29c2-live-proof" --theme "ancient_stoneworks" --sectors 12 --descenders 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed "underreach-29c2-live-proof" --theme "ancient_stoneworks" --sectors 12 --descenders 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$CanonicalJson = Get-Content -Raw $Canonical | ConvertFrom-Json
$ReproJson = Get-Content -Raw $Repro | ConvertFrom-Json
if ($CanonicalJson.protocol -ne "underreach.live-encounter-canonical.v1") { throw "Unexpected 29C.2 canonical protocol: $($CanonicalJson.protocol)" }
if ($CanonicalJson.authoritative -ne $true) { throw "29C.2 canonical proof is not authoritative" }
if ($CanonicalJson.presentation.authoritative -ne $false) { throw "29C.2 presentation contract became authoritative" }
if ($CanonicalJson.digest -ne $ReproJson.digest) { throw "29C.2 identical canonical generation did not reproduce proof digest" }
if ($CanonicalJson.canonical_digest -ne $ReproJson.canonical_digest) { throw "29C.2 identical canonical generation did not reproduce canonical digest" }
$CanonicalHashBefore = (Get-FileHash -Algorithm SHA256 $Canonical).Hash.ToLowerInvariant()

Write-Host "[29C.2] Canonical proof PASS"
Write-Host "canonicalDigest=$($CanonicalJson.canonical_digest) proofDigest=$($CanonicalJson.digest) outcome=$($CanonicalJson.canonical_truth.resolution.outcome)"
Write-Host "ledgerEvents=$($CanonicalJson.canonical_truth.ledger_events.Count) rounds=$($CanonicalJson.canonical_truth.resolution.rounds)"

$StartedUtc = [DateTime]::UtcNow
Write-Host "[29C.2] Unreal canonical encounter consumer proof"
Write-Host "[29C.2] NullRHI enabled so remote validation does not require a desktop/D3D viewport"
Write-Host "[29C.2] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE

if (-not (Test-Path $DebugPath)) {
    Write-Host "[29C.2] FAIL: Unreal proof produced no diagnostics. Unreal exit code: $UnrealExit"
    Write-Host "[29C.2] Relevant Unreal errors:"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29C2" -Context 1,3 | Select-Object -Last 40
    if ($Matches) { $Matches | ForEach-Object { $_.ToString() } | Write-Host }
    else { Get-Content $UnrealLog -Tail 120 | Write-Host }
    throw "29C.2 Unreal proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $DebugPath).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "29C.2 Unreal diagnostics are stale. Unreal exit code: $UnrealExit"
}

$Debug = Get-Content -Raw $DebugPath | ConvertFrom-Json
$CanonicalHashAfter = (Get-FileHash -Algorithm SHA256 $Canonical).Hash.ToLowerInvariant()
$CanonicalDescenderCount = @($CanonicalJson.canonical_truth.participant_final.PSObject.Properties).Count
$CanonicalMonsterCount = @($CanonicalJson.canonical_truth.enemy_final.PSObject.Properties).Count
if ($Debug.protocol -ne "underreach.live-encounter-unreal-debug.v1") { throw "Unexpected 29C.2 Unreal protocol: $($Debug.protocol)" }
if ($Debug.authoritative -ne $false) { throw "29C.2 Unreal presentation became authoritative" }
if (-not $Debug.validation.all_pass) { throw "29C.2 Unreal validation flags failed" }
if ($Debug.canonical_digest -ne $CanonicalJson.canonical_digest) { throw "29C.2 Unreal proof consumed wrong canonical digest" }
if ($CanonicalHashBefore -ne $CanonicalHashAfter) { throw "29C.2 Unreal modified canonical combat artifact" }
if ($Debug.canonical_file_sha256_before -ne $CanonicalHashBefore -or $Debug.canonical_file_sha256_after -ne $CanonicalHashBefore) { throw "29C.2 Unreal canonical file hash evidence is inconsistent" }
if (-not $Debug.validation.defeated_enemy_ids_exact) { throw "29C.2 presentation changed defeated monster set" }
if (-not $Debug.validation.dead_descender_ids_exact) { throw "29C.2 presentation changed dead Descender set" }
if (-not $Debug.validation.retreated_descender_ids_exact) { throw "29C.2 presentation changed retreat set" }
if (-not $Debug.validation.ledger_identity_exact) { throw "29C.2 presentation changed Ledger identity/order" }
if ($Debug.spawned_descenders.Count -ne $CanonicalDescenderCount) { throw "29C.2 Descender actor count differs from canonical state" }
if ($Debug.spawned_monsters.Count -ne $CanonicalMonsterCount) { throw "29C.2 monster actor count differs from canonical state" }

Write-Host "[29C.2] Unreal presentation truth proof PASS"
Write-Host "outcome=$($Debug.outcome) descenders=$($Debug.spawned_descenders.Count) monsters=$($Debug.spawned_monsters.Count) ledgerEvents=$($Debug.ledger_event_count)"
Write-Host "canonicalFileSha256=$CanonicalHashAfter"
if ($UnrealExit -ne 0) {
    Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status."
}

Write-Host "[29C.2] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29C.2] PASS"
Write-Host "Canonical: $Canonical"
Write-Host "Diagnostics: $DebugPath"
Write-Host "Unreal log: $UnrealLog"
