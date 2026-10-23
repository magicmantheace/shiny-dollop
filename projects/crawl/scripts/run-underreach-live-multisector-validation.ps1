param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_live_multisector_proof.py"
$LogDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29b21"
$Output = Join-Path $LogDir "live-multisector-unreal-debug.json"
$Checkpoint = Join-Path $LogDir "live-multisector-checkpoint.json"
$UnrealLog = Join-Path $LogDir "unreal-live-traversal.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29B.2.1 input missing: $Required" }
}

Write-Host "[29B.2.1] Focused deterministic live traversal tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py tests/test_underreach_29b21_live_traversal.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($Generated in @($Output, $Checkpoint, $UnrealLog)) {
    if (Test-Path $Generated) { Remove-Item -Force $Generated }
}
$StartedUtc = [DateTime]::UtcNow

Write-Host "[29B.2.1] Unreal live Descender + Feed traversal proof"
Write-Host "[29B.2.1] NullRHI enabled so remote validation does not require a desktop/D3D viewport"
Write-Host "[29B.2.1] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE

if (-not (Test-Path $Output)) {
    Write-Host "[29B.2.1] FAIL: Unreal proof produced no diagnostics. Unreal exit code: $UnrealExit"
    Write-Host "[29B.2.1] Relevant Unreal errors:"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29B21" -Context 1,3 | Select-Object -Last 35
    if ($Matches) { $Matches | ForEach-Object { $_.ToString() } | Write-Host }
    else { Get-Content $UnrealLog -Tail 100 | Write-Host }
    throw "29B.2.1 Unreal proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $Output).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "29B.2.1 Unreal diagnostics are stale. Unreal exit code: $UnrealExit"
}
if (-not (Test-Path $Checkpoint)) { throw "29B.2.1 produced no traversal checkpoint" }

$Debug = Get-Content -Raw $Output | ConvertFrom-Json
if ($Debug.protocol -ne "underreach.live-multisector-unreal-debug.v1") { throw "Unexpected 29B.2.1 protocol: $($Debug.protocol)" }
if ($Debug.authoritative -ne $false) { throw "29B.2.1 presentation proof became authoritative" }
if (-not $Debug.validation.all_pass) { throw "29B.2.1 Unreal validation flags failed" }
if (@($Debug.route_sector_ids).Count -lt 2) { throw "29B.2.1 route did not cross Sectors" }
if ([int]$Debug.sector_transition_count -ne (@($Debug.route_sector_ids).Count - 1)) { throw "29B.2.1 transition count mismatch" }
if ([int]$Debug.empty_camera_windows -ne 0) { throw "29B.2.1 Follow/Auto Feed had empty camera windows" }
if ([int]$Debug.stale_target_windows -ne 0) { throw "29B.2.1 Follow/Auto Feed had stale targets" }
if ([double]$Debug.max_descender_error_cm -gt 0.01) { throw "29B.2.1 Descender actor diverged from traversal stream" }
if ([double]$Debug.max_follow_camera_error_cm -gt 0.01 -or [double]$Debug.max_auto_camera_error_cm -gt 0.01) { throw "29B.2.1 camera actors diverged from Feed stream" }
if ($Debug.checkpoint_current_sector_id -eq $null) { throw "29B.2.1 checkpoint did not preserve current Sector" }

Write-Host "[29B.2.1] Unreal live traversal PASS"
Write-Host "frames=$($Debug.frame_count) routeSectors=$(@($Debug.route_sector_ids).Count) transitions=$($Debug.sector_transition_count)"
Write-Host "emptyCameraWindows=$($Debug.empty_camera_windows) staleTargetWindows=$($Debug.stale_target_windows)"
Write-Host "checkpointSector=$($Debug.checkpoint_current_sector_id) resumeFrames=$($Debug.resume_frame_count)"
Write-Host "stratumDigest=$($Debug.stratum_environment_digest)"
Write-Host "multisectorDigest=$($Debug.multisector_digest)"
Write-Host "liveTraversalDigest=$($Debug.live_traversal_digest)"
if ($UnrealExit -ne 0) {
    Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status."
}

Write-Host "[29B.2.1] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29B.2.1] PASS"
Write-Host "Diagnostics: $Output"
Write-Host "Checkpoint: $Checkpoint"
Write-Host "Unreal log: $UnrealLog"
