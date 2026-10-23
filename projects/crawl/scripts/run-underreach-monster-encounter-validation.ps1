param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_monster_encounter_proof.py"
$LogDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29c1"
$Output = Join-Path $LogDir "monster-encounter-unreal-debug.json"
$UnrealLog = Join-Path $LogDir "unreal-monster-encounter-proof.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29C.1 input missing: $Required" }
}

Write-Host "[29C.1] Focused deterministic monster encounter tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py tests/test_underreach_29b21_live_traversal.py tests/test_underreach_29b3_stratum_theme.py tests/test_underreach_29c1_monster_encounters.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($Generated in @($Output, $UnrealLog)) {
    if (Test-Path $Generated) { Remove-Item -Force $Generated }
}
$StartedUtc = [DateTime]::UtcNow

Write-Host "[29C.1] Unreal monster encounter construction proof"
Write-Host "[29C.1] NullRHI enabled so remote validation does not require a desktop/D3D viewport"
Write-Host "[29C.1] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE

if (-not (Test-Path $Output)) {
    Write-Host "[29C.1] FAIL: Unreal proof produced no diagnostics. Unreal exit code: $UnrealExit"
    Write-Host "[29C.1] Relevant Unreal errors:"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29C1" -Context 1,3 | Select-Object -Last 35
    if ($Matches) { $Matches | ForEach-Object { $_.ToString() } | Write-Host }
    else { Get-Content $UnrealLog -Tail 100 | Write-Host }
    throw "29C.1 Unreal proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $Output).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "29C.1 Unreal diagnostics are stale. Unreal exit code: $UnrealExit"
}

$Debug = Get-Content -Raw $Output | ConvertFrom-Json
if ($Debug.protocol -ne "underreach.monster-encounter-unreal-debug.v1") { throw "Unexpected 29C.1 protocol: $($Debug.protocol)" }
if ($Debug.authoritative -ne $false) { throw "29C.1 presentation proof became authoritative" }
if (-not $Debug.validation.all_pass) { throw "29C.1 Unreal validation flags failed" }
if ([int]$Debug.sector_count -lt 4) { throw "29C.1 proof has too few Sectors" }
if ([int]$Debug.encounter_count -lt 1 -or [int]$Debug.monster_count -lt 1) { throw "29C.1 spawned no meaningful encounters" }
if ([int]$Debug.safe_sector_spawn_count -ne 0) { throw "29C.1 spawned monsters in Entry/Refuge" }
if ([double]$Debug.max_actor_location_error_cm -gt 0.01) { throw "29C.1 Unreal monster actor placement diverged from encounter plan" }
if ([double]$Debug.max_spawn_clearance_ratio -gt 1.0) { throw "29C.1 monster spawn exceeded combat clearance" }
if (-not $Debug.validation.topology_preserved) { throw "29C.1 encounter generation changed Stratum topology" }
if (-not $Debug.validation.promotion_required_for_canonical_combat) { throw "29C.1 lost simulation promotion boundary" }

Write-Host "[29C.1] Unreal monster encounter proof PASS"
Write-Host "sectors=$($Debug.sector_count) encounters=$($Debug.encounter_count) monsters=$($Debug.monster_count) archetypes=$($Debug.monster_archetype_count)"
Write-Host "safeSectorSpawns=$($Debug.safe_sector_spawn_count) maxPlacementErrorCm=$($Debug.max_actor_location_error_cm)"
Write-Host "stratumDigest=$($Debug.stratum_environment_digest)"
Write-Host "themeDigest=$($Debug.theme_digest)"
Write-Host "encounterDigest=$($Debug.encounter_plan_digest)"
Write-Host "monsterDefinitionsDigest=$($Debug.monster_definition_digest)"
if ($UnrealExit -ne 0) {
    Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status."
}

Write-Host "[29C.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29C.1] PASS"
Write-Host "Diagnostics: $Output"
Write-Host "Unreal log: $UnrealLog"
