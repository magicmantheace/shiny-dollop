param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_multisector_proof.py"
$Output = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29b2\multisector-unreal-debug.json"
$LogDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29b2"
$UnrealLog = Join-Path $LogDir "unreal-proof.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29B.2 input missing: $Required" }
}

Write-Host "[29B.2] Focused deterministic multi-Sector tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Output) { Remove-Item -Force $Output }
if (Test-Path $UnrealLog) { Remove-Item -Force $UnrealLog }
$StartedUtc = [DateTime]::UtcNow

Write-Host "[29B.2] Unreal multi-Sector construction proof"
Write-Host "[29B.2] NullRHI enabled so validation does not require a desktop/D3D viewport"
Write-Host "[29B.2] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE

if (-not (Test-Path $Output)) {
    Write-Host "[29B.2] FAIL: Unreal proof produced no diagnostics. Unreal exit code: $UnrealExit"
    Write-Host "[29B.2] Relevant Unreal errors:"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29B2|NullRHI" -Context 1,3 | Select-Object -Last 30
    if ($Matches) {
        $Matches | ForEach-Object { $_.ToString() } | Write-Host
    } else {
        Get-Content $UnrealLog -Tail 80 | Write-Host
    }
    throw "29B.2 Unreal proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $Output).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "29B.2 Unreal proof diagnostics are stale. Unreal exit code: $UnrealExit"
}

$Debug = Get-Content -Raw $Output | ConvertFrom-Json
if ($Debug.protocol -ne "underreach.multisector-unreal-debug.v1") { throw "Unexpected 29B.2 debug protocol: $($Debug.protocol)" }
if ($Debug.authoritative -ne $false) { throw "29B.2 presentation proof became authoritative" }
if (-not $Debug.validation.all_pass) { throw "29B.2 Unreal validation flags failed" }
if ([int]$Debug.room_count -lt 4) { throw "29B.2 spawned too few rooms" }
if ([int]$Debug.corridor_count -ne [int]$Debug.connection_count) { throw "29B.2 corridor/connection mismatch" }
if (@($Debug.route_sector_ids).Count -lt 2) { throw "29B.2 proof route did not cross Sectors" }
if ([int]$Debug.camera_handoff_window_count -ne (@($Debug.route_sector_ids).Count - 1)) { throw "29B.2 camera handoff count does not match route hops" }
if ([int]$Debug.empty_camera_windows -ne 0 -or [int]$Debug.stale_target_windows -ne 0) { throw "29B.2 reported empty/stale camera windows" }

Write-Host "[29B.2] Unreal proof PASS"
Write-Host "rooms=$($Debug.room_count) corridors=$($Debug.corridor_count) routeSectors=$(@($Debug.route_sector_ids).Count) actors=$($Debug.spawned_actor_count)"
Write-Host "stratumDigest=$($Debug.stratum_environment_digest)"
Write-Host "multisectorDigest=$($Debug.multisector_digest)"
if ($UnrealExit -ne 0) {
    Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status."
}

Write-Host "[29B.2] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29B.2] PASS"
Write-Host "Diagnostics: $Output"
Write-Host "Unreal log: $UnrealLog"
