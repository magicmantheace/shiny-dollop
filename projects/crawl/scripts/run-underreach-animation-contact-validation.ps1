param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Profiler = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\profile_mannequin_attacks.py"
$Profiles = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\attack_profiles_measured.json"
$Generator = Join-Path $RepoRoot "scripts\generate-underreach-animation-binding-proof.py"
$Builder = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_animation_binding_proof.py"
$OutputDir = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29d2"
$Proof = Join-Path $OutputDir "animation-binding-proof.json"
$Repro = Join-Path $OutputDir "animation-binding-proof-repro.json"
$Debug = Join-Path $OutputDir "animation-binding-unreal-debug.json"
$ProfilerLog = Join-Path $OutputDir "unreal-attack-profiler.log"
$UnrealLog = Join-Path $OutputDir "unreal-animation-binding-proof.log"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($Required in @($UnrealEditorCmd, $Project, $Profiler, $Generator, $Builder)) {
    if (-not (Test-Path $Required)) { throw "Required 29D.2 input missing: $Required" }
}

Write-Host "[29D.2] Focused deterministic animation binding tests"
& $Python -m pytest -q tests/test_underreach_29b1_stratum_environment.py tests/test_underreach_29b2_multisector.py tests/test_underreach_29b21_live_traversal.py tests/test_underreach_29b3_stratum_theme.py tests/test_underreach_29c1_monster_encounters.py tests/test_underreach_29c2_live_encounters.py tests/test_underreach_29c3_autonomous_encounters.py tests/test_underreach_29d1_combat_presentation.py tests/test_underreach_29d2_animation_binding.py tests/test_attack_variety.py tests/test_animation_transitions.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($Generated in @($Profiles, $Proof, $Repro, $Debug, $ProfilerLog, $UnrealLog)) {
    if (Test-Path $Generated) { Remove-Item -Force $Generated }
}

Write-Host "[29D.2] Measuring real Manny attack assets with deterministic AnimPose"
Write-Host "[29D.2] NullRHI enabled so profiling does not require a desktop/D3D viewport"
$ProfileStartedUtc = [DateTime]::UtcNow
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Profiler" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $ProfilerLog
$ProfilerExit = $LASTEXITCODE
if (-not (Test-Path $Profiles)) {
    Write-Host "[29D.2] FAIL: attack profiler produced no measurement artifact. Unreal exit code: $ProfilerExit"
    Get-Content $ProfilerLog -Tail 120 | Write-Host
    throw "29D.2 attack profiler produced no measurement JSON"
}
if ((Get-Item $Profiles).LastWriteTimeUtc -lt $ProfileStartedUtc.AddSeconds(-1)) {
    throw "29D.2 attack profile measurements are stale. Unreal exit code: $ProfilerExit"
}
$Measured = Get-Content -Raw $Profiles | ConvertFrom-Json
if ($Measured.protocol -ne "crawl.presentation-attack-profile-measurements.v3") { throw "Unexpected 29D.2 profile protocol: $($Measured.protocol)" }
if ($Measured.authoritative -ne $false) { throw "29D.2 measured attack profiles became authoritative" }
if ($Measured.evaluation_mode -ne "anim_pose_component_space_root_locked") { throw "29D.2 profiler used unexpected evaluation mode" }
$RequiredAttacks = @("MM_Attack_01", "MM_Attack_02", "MM_Attack_03", "MM_ChargedAttack")
$MeasuredNames = @($Measured.profiles | ForEach-Object { $_.asset_name })
foreach ($Name in $RequiredAttacks) {
    if ($MeasuredNames -notcontains $Name) { throw "29D.2 required real attack asset was not measured: $Name" }
}
if (@($Measured.missing_assets).Count -ne 0) { throw "29D.2 attack profiler reports missing assets: $($Measured.missing_assets -join ', ')" }
foreach ($Profile in @($Measured.profiles)) {
    $V = $Profile.pose_variation
    if ($null -eq $V -or ([int]$V.unique_forward -le 8 -and [int]$V.unique_lateral -le 8 -and [int]$V.unique_height -le 8)) {
        throw "29D.2 profiler detected frozen source animation: $($Profile.asset_name)"
    }
}
Write-Host "[29D.2] Real attack profile measurement PASS"
foreach ($Profile in @($Measured.profiles | Where-Object { $RequiredAttacks -contains $_.asset_name })) {
    Write-Host ("  {0}: effector={1} phase={2:N4} reach={3:N2}cm duration={4:N3}s" -f $Profile.asset_name, $Profile.contact_effector, [double]$Profile.candidate_contact_phase, [double]$Profile.candidate_forward_reach_cm, [double]$Profile.source_duration_seconds)
}
if ($ProfilerExit -ne 0) { Write-Warning "Unreal profiler returned $ProfilerExit after writing fresh valid measurements; accepting artifact validation rather than shutdown status." }

Write-Host "[29D.2] Generating real-animation binding proof twice for reproducibility"
& $Python $Generator --profiles $Profiles --output $Proof --seed "underreach-29d2-animation-contact-proof"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python $Generator --profiles $Profiles --output $Repro --seed "underreach-29d2-animation-contact-proof"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$ProofJson = Get-Content -Raw $Proof | ConvertFrom-Json
$ReproJson = Get-Content -Raw $Repro | ConvertFrom-Json
if ($ProofJson.binding.protocol -ne "underreach.animation-binding.v1") { throw "Unexpected 29D.2 binding protocol: $($ProofJson.binding.protocol)" }
if ($ProofJson.binding.authoritative -ne $false) { throw "29D.2 animation binding became authoritative" }
if ($ProofJson.binding.digest -ne $ReproJson.binding.digest) { throw "29D.2 identical input did not reproduce binding digest" }
if ($ProofJson.combat_proof.presentation.digest -ne $ReproJson.combat_proof.presentation.digest) { throw "29D.2 identical input did not reproduce 29D.1 presentation digest" }
$AttackBindings = @($ProofJson.binding.bindings | Where-Object { $_.presentation_kind -eq "attack" })
if ($AttackBindings.Count -lt 1) { throw "29D.2 proof contains no real attack bindings" }
foreach ($Name in $RequiredAttacks) {
    if (@($AttackBindings.asset_name) -notcontains $Name) { throw "29D.2 proof did not exercise real asset $Name" }
}
$FalseRealFallback = @($ProofJson.binding.bindings | Where-Object { $_.binding_status -eq "semantic_fallback" -and $null -ne $_.asset_path }).Count
if ($FalseRealFallback -ne 0) { throw "29D.2 falsely attached a real asset to semantic fallback" }
Write-Host "[29D.2] Deterministic animation binding schedule PASS"
Write-Host "sourceDigest=$($ProofJson.binding.source_canonical_digest) presentationDigest=$($ProofJson.binding.source_presentation_digest) bindingDigest=$($ProofJson.binding.digest)"
Write-Host "attackBindings=$($AttackBindings.Count) uniqueAssets=$(@($AttackBindings.asset_name | Sort-Object -Unique).Count) semanticFallbacks=$(@($ProofJson.binding.bindings | Where-Object { $_.binding_status -eq 'semantic_fallback' }).Count)"

$ProofHashBefore = (Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
$UnrealStartedUtc = [DateTime]::UtcNow
Write-Host "[29D.2] Unreal real-animation contact consumer proof"
Write-Host "[29D.2] NullRHI enabled so validation does not require a desktop/D3D viewport"
Write-Host "[29D.2] Unreal output is being captured to: $UnrealLog"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit = $LASTEXITCODE
if (-not (Test-Path $Debug)) {
    Write-Host "[29D.2] FAIL: Unreal proof produced no diagnostics. Unreal exit code: $UnrealExit"
    $Matches = Select-String -Path $UnrealLog -Pattern "Traceback|Python Error|LogPython: Error|Error:|Exception|Underreach29D2" -Context 1,3 | Select-Object -Last 40
    if ($Matches) { $Matches | ForEach-Object { $_.ToString() } | Write-Host } else { Get-Content $UnrealLog -Tail 120 | Write-Host }
    throw "29D.2 Unreal proof produced no diagnostics. See $UnrealLog"
}
if ((Get-Item $Debug).LastWriteTimeUtc -lt $UnrealStartedUtc.AddSeconds(-1)) { throw "29D.2 Unreal diagnostics are stale. Unreal exit code: $UnrealExit" }
$DebugJson = Get-Content -Raw $Debug | ConvertFrom-Json
$ProofHashAfter = (Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if ($DebugJson.protocol -ne "underreach.animation-binding-unreal-debug.v1") { throw "Unexpected 29D.2 Unreal protocol: $($DebugJson.protocol)" }
if ($DebugJson.authoritative -ne $false) { throw "29D.2 Unreal proof became authoritative" }
if (-not $DebugJson.validation.all_pass) { throw "29D.2 Unreal validation flags failed" }
if ($ProofHashBefore -ne $ProofHashAfter) { throw "29D.2 Unreal modified binding proof artifact" }
if ([int]$DebugJson.unique_attack_asset_count -lt 4) { throw "29D.2 Unreal did not consume all four real attack assets" }
if ([int]$DebugJson.evaluated_contact_count -ne [int]$DebugJson.attack_window_count) { throw "29D.2 Unreal did not evaluate every bound attack contact" }
if ([double]$DebugJson.max_profile_reach_delta_cm -gt 1.0) { throw "29D.2 Unreal contact geometry diverged from measured profile" }
if (@($DebugJson.missing_assets).Count -ne 0 -or @($DebugJson.invalid_poses).Count -ne 0 -or @($DebugJson.frozen_assets).Count -ne 0) { throw "29D.2 Unreal reported missing, invalid, or frozen real animation assets" }
Write-Host "[29D.2] Unreal real-animation contact proof PASS"
Write-Host "attacks=$($DebugJson.attack_window_count) assets=$($DebugJson.unique_attack_asset_count) contacts=$($DebugJson.evaluated_contact_count) fallbacks=$($DebugJson.semantic_fallback_count)"
Write-Host "maxReachDeltaCm=$($DebugJson.max_profile_reach_delta_cm) maxAlignmentCm=$($DebugJson.max_alignment_request_cm) maxFacingDeltaDeg=$($DebugJson.max_facing_delta_degrees)"
if ($UnrealExit -ne 0) { Write-Warning "Unreal returned $UnrealExit after writing fresh valid diagnostics; accepting artifact validation rather than shutdown status." }

Write-Host "[29D.2] Full repository regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[29D.2] PASS"
Write-Host "Profiles: $Profiles"
Write-Host "Proof: $Proof"
Write-Host "Diagnostics: $Debug"
Write-Host "Profiler log: $ProfilerLog"
Write-Host "Unreal log: $UnrealLog"
