param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_stratum_theme_proof.py"
$Output = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29b3\stratum-theme-unreal-debug.json"
$LogDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29b3"
$UnrealLog = Join-Path $LogDir "unreal-theme-proof.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29B.3 input missing: $Required" }
}

Write-Host "[29B.3] Focused deterministic Stratum theme tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py tests/test_underreach_29b21_live_traversal.py tests/test_underreach_29b3_stratum_theme.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path $Output) { Remove-Item -Force $Output }
if (Test-Path $UnrealLog) { Remove-Item -Force $UnrealLog }
$StartedUtc = [DateTime]::UtcNow

Write-Host "[29B.3] Unreal deterministic theme application proof"
Write-Host "[29B.3] NullRHI enabled so remote validation does not require a desktop/D3D viewport"
Write-Host "[29B.3] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE

if (-not (Test-Path $Output)) {
    Write-Host "[29B.3] FAIL: Unreal theme proof produced no diagnostics. Unreal exit code: $UnrealExit"
    Write-Host "[29B.3] Relevant Unreal errors:"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29B3" -Context 1,3 | Select-Object -Last 30
    if ($Matches) { $Matches | ForEach-Object { $_.ToString() } | Write-Host }
    else { Get-Content $UnrealLog -Tail 80 | Write-Host }
    throw "29B.3 Unreal theme proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $Output).LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-1)) {
    throw "29B.3 Unreal theme diagnostics are stale. Unreal exit code: $UnrealExit"
}

$Debug = Get-Content -Raw $Output | ConvertFrom-Json
if ($Debug.protocol -ne "underreach.stratum-theme-unreal-debug.v1") { throw "Unexpected 29B.3 debug protocol: $($Debug.protocol)" }
if ($Debug.authoritative -ne $false) { throw "29B.3 presentation theme proof became authoritative" }
if (-not $Debug.validation.all_pass) { throw "29B.3 Unreal validation flags failed" }
if ([int]$Debug.theme_count -lt 3) { throw "29B.3 did not prove at least three themes" }
if ([int]$Debug.sector_count -lt 4) { throw "29B.3 spawned too few Sectors" }
if ([int]$Debug.spawned_actor_count -ne ([int]$Debug.theme_count * [int]$Debug.sector_count)) { throw "29B.3 themed actor count mismatch" }
if (-not $Debug.validation.topology_equal_across_themes) { throw "29B.3 theme changed topology" }
if (-not $Debug.validation.all_theme_digests_unique) { throw "29B.3 distinct themes did not produce distinct visual digests" }
if (-not $Debug.validation.theme_metadata_applied_to_unreal_actors) { throw "29B.3 Unreal actors did not receive deterministic theme metadata" }

Write-Host "[29B.3] Unreal theme proof PASS"
Write-Host "themes=$($Debug.theme_count) sectors=$($Debug.sector_count) actors=$($Debug.spawned_actor_count)"
Write-Host "stratumDigest=$($Debug.stratum_environment_digest)"
$Debug.theme_digests.PSObject.Properties | ForEach-Object { Write-Host "$($_.Name)Digest=$($_.Value)" }
if ($UnrealExit -ne 0) {
    Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status."
}

Write-Host "[29B.3] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29B.3] PASS"
Write-Host "Diagnostics: $Output"
Write-Host "Unreal log: $UnrealLog"
