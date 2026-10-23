param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generator = Join-Path $RepoRoot "scripts\generate-underreach-combat-presentation-proof.py"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_combat_presentation_proof.py"
$OutputDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29d1"
$Proof = Join-Path $OutputDir "combat-presentation-proof.json"
$Repro = Join-Path $OutputDir "combat-presentation-proof-repro.json"
$DebugPath = Join-Path $OutputDir "combat-presentation-unreal-debug.json"
$UnrealLog = Join-Path $OutputDir "unreal-combat-presentation-proof.log"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Generator, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29D.1 input missing: $Required" }
}

Write-Host "[29D.1] Focused deterministic combat presentation tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py tests/test_underreach_29b21_live_traversal.py tests/test_underreach_29b3_stratum_theme.py tests/test_underreach_29c1_monster_encounters.py tests/test_underreach_29c2_live_encounters.py tests/test_underreach_29c3_autonomous_encounters.py tests/test_underreach_29d1_combat_presentation.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($Generated in @($Proof, $Repro, $DebugPath, $UnrealLog)) {
    if (Test-Path $Generated) { Remove-Item -Force $Generated }
}

Write-Host "[29D.1] Generating presentation proof twice for reproducibility"
& $Python $Generator --output $Proof --seed "underreach-29d1-combat-presentation-proof"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --output $Repro --seed "underreach-29d1-combat-presentation-proof"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$ProofJson = Get-Content -Raw $Proof | ConvertFrom-Json
$ReproJson = Get-Content -Raw $Repro | ConvertFrom-Json
if ($ProofJson.source.protocol -ne "underreach.autonomous-encounter-flow.v1") { throw "29D.1 source protocol unexpected" }
if ($ProofJson.source.authoritative -ne $true) { throw "29D.1 source is not authoritative" }
if ($ProofJson.presentation.protocol -ne "underreach.combat-presentation.v1") { throw "29D.1 presentation protocol unexpected" }
if ($ProofJson.presentation.authoritative -ne $false) { throw "29D.1 presentation became authoritative" }
if ($ProofJson.presentation.canonical_state_mutation_allowed -ne $false) { throw "29D.1 presentation gained canonical mutation authority" }
if ($ProofJson.presentation.simulation_time_independent -ne $true) { throw "29D.1 simulation/presentation clocks are not separated" }
if ($ProofJson.source.canonical_digest -ne $ReproJson.source.canonical_digest) { throw "29D.1 source canonical digest did not reproduce" }
if ($ProofJson.presentation.digest -ne $ReproJson.presentation.digest) { throw "29D.1 presentation digest did not reproduce" }
if ($ProofJson.presentation.source_canonical_digest -ne $ProofJson.source.canonical_digest) { throw "29D.1 presentation not bound to source canonical digest" }
if ([int]$ProofJson.presentation.windows.Count -lt 1) { throw "29D.1 produced no presentation windows" }
$Attacks = @($ProofJson.presentation.windows | Where-Object { $_.presentation_kind -eq "attack" }).Count
$Reactions = @($ProofJson.presentation.windows | Where-Object { $_.presentation_kind -eq "hit_reaction" }).Count
$Locomotion = @($ProofJson.presentation.windows | Where-Object { $_.presentation_kind -eq "locomotion" }).Count
if ($Attacks -lt 1) { throw "29D.1 produced no attack presentation windows" }
if ($Reactions -lt 1) { throw "29D.1 produced no canonical hit reactions" }
if ($Locomotion -lt 1) { throw "29D.1 produced no locomotion presentation windows" }
$ProofHashBefore = (Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()

Write-Host "[29D.1] Deterministic presentation schedule PASS"
Write-Host "sourceDigest=$($ProofJson.source.canonical_digest) presentationDigest=$($ProofJson.presentation.digest) outcome=$($ProofJson.source.canonical_truth.outcome)"
Write-Host "frames=$($ProofJson.source.canonical_truth.frames.Count) windows=$($ProofJson.presentation.windows.Count) attacks=$Attacks reactions=$Reactions locomotion=$Locomotion durationSec=$($ProofJson.presentation.presentation_duration_seconds)"

$StartedUtc = [DateTime]::UtcNow
Write-Host "[29D.1] Unreal combat presentation consumer proof"
Write-Host "[29D.1] NullRHI enabled so remote validation does not require a desktop/D3D viewport"
Write-Host "[29D.1] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE

if (-not (Test-Path $DebugPath)) {
    Write-Host "[29D.1] FAIL: Unreal proof produced no diagnostics. Unreal exit code: $UnrealExit"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29D1" -Context 1,3 | Select-Object -Last 40
    if ($Matches) { $Matches | ForEach-Object { $_.ToString() } | Write-Host }
    else { Get-Content $UnrealLog -Tail 120 | Write-Host }
    throw "29D.1 Unreal proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $DebugPath).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "29D.1 Unreal diagnostics are stale. Unreal exit code: $UnrealExit"
}

$Debug = Get-Content -Raw $DebugPath | ConvertFrom-Json
$ProofHashAfter = (Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if ($Debug.protocol -ne "underreach.combat-presentation-unreal-debug.v1") { throw "Unexpected 29D.1 Unreal protocol: $($Debug.protocol)" }
if ($Debug.authoritative -ne $false) { throw "29D.1 Unreal presentation became authoritative" }
if (-not $Debug.validation.all_pass) { throw "29D.1 Unreal validation flags failed" }
if ($Debug.source_canonical_digest -ne $ProofJson.source.canonical_digest) { throw "29D.1 Unreal consumed wrong canonical source" }
if ($Debug.presentation_digest -ne $ProofJson.presentation.digest) { throw "29D.1 Unreal consumed wrong presentation schedule" }
if ($ProofHashBefore -ne $ProofHashAfter) { throw "29D.1 Unreal modified proof artifact" }
if ($Debug.proof_file_sha256_before -ne $ProofHashBefore -or $Debug.proof_file_sha256_after -ne $ProofHashBefore) { throw "29D.1 Unreal proof hash evidence inconsistent" }
if ([int]$Debug.window_count -ne [int]$ProofJson.presentation.windows.Count) { throw "29D.1 Unreal did not consume every presentation window" }
if ([int]$Debug.empty_feed_focus_windows -ne 0 -or [int]$Debug.stale_feed_focus_windows -ne 0) { throw "29D.1 Feed focus became empty/stale" }
if ([double]$Debug.max_actor_location_error_cm -gt 0.01) { throw "29D.1 presentation actor position diverged from canonical frame" }
if ([double]$Debug.max_facing_yaw_error_degrees -gt 0.01) { throw "29D.1 actor facing diverged from presentation schedule" }
if ([int]$Debug.attack_window_count -lt 1 -or [int]$Debug.reaction_window_count -lt 1) { throw "29D.1 Unreal did not present attacks/reactions" }
if ($Debug.camera_shots.Count -lt 2) { throw "29D.1 Feed camera did not vary by action" }

Write-Host "[29D.1] Unreal combat presentation proof PASS"
Write-Host "outcome=$($Debug.outcome) actors=$($Debug.actor_count) windows=$($Debug.window_count) attacks=$($Debug.attack_window_count) reactions=$($Debug.reaction_window_count) deaths=$($Debug.death_window_count)"
Write-Host "shots=$($Debug.camera_shots.Count) semanticSlots=$($Debug.semantic_slots_applied) maxActorErrorCm=$($Debug.max_actor_location_error_cm) maxYawErrorDeg=$($Debug.max_facing_yaw_error_degrees)"
if ($UnrealExit -ne 0) {
    Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status."
}

Write-Host "[29D.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29D.1] PASS"
Write-Host "Proof: $Proof"
Write-Host "Diagnostics: $DebugPath"
Write-Host "Unreal log: $UnrealLog"
