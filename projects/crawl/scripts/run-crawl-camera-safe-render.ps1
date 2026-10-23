param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$CameraSafeBuild = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_vertical_slice_dungeon.py"
$Manifest = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\stage_manifest.json"
$AnimationPlan = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\animation_plan.json"
$EnvironmentManifest = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\environment_manifest.json"
$EnvironmentGenerator = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\dungeon_environment.py"
$AssetRegistry = Join-Path $RepoRoot "unreal\CrawlPresentation\presentation_assets.json"
$UnrealResult = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\unreal_build_result.json"
$UnrealLog = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\Logs\death-persistence-build.log"
$ContinueScript = Join-Path $RepoRoot "scripts\continue-crawl-unreal-render.ps1"

foreach ($required in @($Python, $UnrealEditorCmd, $Project, $CameraSafeBuild, $EnvironmentGenerator, $Manifest, $AnimationPlan, $AssetRegistry, $ContinueScript)) {
    if (-not (Test-Path $required)) { throw "Required Slice 28A render input missing: $required" }
}

Write-Host "== Slice 28A.5 dungeon + death + variety + transition + combat + camera focused tests =="
& $Python -m pytest `
    tests/test_dungeon_environment.py `
    tests/test_death_persistence.py `
    tests/test_attack_variety.py `
    tests/test_animation_transitions.py `
    tests/test_combat_staging.py `
    tests/test_unreal_camera_planning.py `
    tests/test_presentation_animation.py `
    tests/test_crawl_unreal_vertical_slice.py `
    -q
if ($LASTEXITCODE -ne 0) { throw "Slice 28A focused tests failed with exit code $LASTEXITCODE" }

Write-Host "== Generate deterministic dungeon environment manifest =="
& $Python $EnvironmentGenerator `
    --stage-manifest $Manifest `
    --output $EnvironmentManifest
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $EnvironmentManifest)) {
    throw "Dungeon environment manifest generation failed with exit code $LASTEXITCODE"
}

$env:CRAWL_STAGE_MANIFEST = (Resolve-Path $Manifest).Path
$env:CRAWL_ANIMATION_PLAN = (Resolve-Path $AnimationPlan).Path
$env:CRAWL_PRESENTATION_ASSETS = (Resolve-Path $AssetRegistry).Path
$env:CRAWL_ENVIRONMENT_MANIFEST = (Resolve-Path $EnvironmentManifest).Path

Write-Host "== Build Crawl scene with terminal corpse persistence =="
$UnrealLogDirectory = Split-Path -Parent $UnrealLog
New-Item -ItemType Directory -Force -Path $UnrealLogDirectory | Out-Null
if (Test-Path -LiteralPath $UnrealLog) { Remove-Item -LiteralPath $UnrealLog -Force }
$BuildStartedUtc = [DateTime]::UtcNow
& $UnrealEditorCmd $Project "-ExecutePythonScript=$CameraSafeBuild" -unattended -nop4 -nosplash -log "-abslog=$UnrealLog"
$BuildExit = $LASTEXITCODE

function Write-UnrealFailureContext {
    if (-not (Test-Path -LiteralPath $UnrealLog)) {
        Write-Warning "Unreal diagnostic log was not created: $UnrealLog"
        return
    }
    Write-Host ""
    Write-Host "== Unreal failure context from $UnrealLog ==" -ForegroundColor Yellow
    $Patterns = "LogPython: Error|Traceback|RuntimeError|AssertionError|ensure condition failed|Fatal error|Error:"
    $Matches = Select-String -LiteralPath $UnrealLog -Pattern $Patterns -Context 5, 12
    if ($Matches) {
        $Matches | ForEach-Object { $_.Context.PreContext; $_.Line; $_.Context.PostContext; "" }
    }
    else {
        Get-Content -LiteralPath $UnrealLog -Tail 80
    }
}

if (-not (Test-Path $UnrealResult)) {
    Write-UnrealFailureContext
    throw "Unreal build produced no metadata. Unreal exit code: $BuildExit"
}
if ((Get-Item $UnrealResult).LastWriteTimeUtc -lt $BuildStartedUtc.AddSeconds(-1)) {
    Write-UnrealFailureContext
    throw "Unreal build left stale metadata. Unreal exit code: $BuildExit"
}

$ManifestData = Get-Content $Manifest -Raw | ConvertFrom-Json
$AnimationData = Get-Content $AnimationPlan -Raw | ConvertFrom-Json
$Build = Get-Content $UnrealResult -Raw | ConvertFrom-Json
if ($Build.manifest_digest -ne $ManifestData.digest) { throw "Generated scene does not match current staging manifest." }
if ($Build.animation_plan_digest -ne $AnimationData.digest) { throw "Generated scene does not match current animation plan." }
if (-not $Build.level_asset -or -not $Build.sequence_asset) { throw "Generated scene metadata is incomplete." }
if ($Build.camera_architecture -ne "time_aware_safe_master_tracking" -or -not (Test-Path $Build.camera_debug)) { throw "Accepted camera validation regressed." }
if (-not $Build.combat_debug -or -not (Test-Path $Build.combat_debug)) { throw "Combat diagnostics missing." }
if (-not $Build.death_debug -or -not (Test-Path $Build.death_debug)) { throw "Death-persistence diagnostics missing." }
if ($Build.environment_protocol -ne "crawl.presentation-environment.v1" -or -not $Build.environment_debug -or -not (Test-Path $Build.environment_debug)) { throw "Dungeon environment diagnostics missing." }

$Environment = Get-Content $Build.environment_debug -Raw | ConvertFrom-Json
if ([bool]$Environment.authoritative -or -not [bool]$Environment.camera_obstruction_checks.all_samples_valid) { throw "Dungeon environment authority/camera validation failed." }
if ([int]$Environment.module_count -lt 8 -or [int]$Environment.light_count -lt 4) { throw "Dungeon room is incomplete." }
if (@($Environment.actor_floor_checks | Where-Object { -not [bool]$_.valid }).Count -gt 0) { throw "Dungeon actor-floor validation failed." }

$Combat = Get-Content $Build.combat_debug -Raw | ConvertFrom-Json
foreach ($Attack in @($Combat.attacks)) {
    if ($null -eq $Attack.evaluated_contact_planar_error_cm -or $null -eq $Attack.evaluated_contact_error_cm) { throw "Rendered contact was not evaluated for $($Attack.attack_id)." }
    if ([double]$Attack.evaluated_contact_planar_error_cm -gt [double]$Attack.maximum_evaluated_planar_error_cm -or [double]$Attack.evaluated_contact_error_cm -gt [double]$Attack.maximum_evaluated_contact_error_cm) { throw "Combat contact validation failed for $($Attack.attack_id)." }
}

$Death = Get-Content $Build.death_debug -Raw | ConvertFrom-Json
foreach ($Actor in @($Death.actors)) {
    if (-not [bool]$Actor.persistent -or [double]$Actor.maximum_bone_delta_cm -gt 2.0) { throw "Corpse pose did not persist for $($Actor.actor_id)." }
    if (@($Actor.samples).Count -lt 4 -or -not [bool]$Actor.transform_stable -or -not [bool]$Actor.orientation_stable) { throw "Corpse multi-sample stability validation failed for $($Actor.actor_id)." }
}

$SkeletalCount = @($Build.presentation_assets.skeletal_actor_ids).Count
$AnimationSections = [int]$Build.presentation_assets.animation_section_count
if ($SkeletalCount -lt 1 -or $AnimationSections -lt 1 -or @($Build.presentation_assets.animation_errors).Count -gt 0) { throw "Skeletal presentation bindings regressed." }

if ($BuildExit -ne 0) { Write-Warning "Unreal returned exit code $BuildExit after writing valid artifacts." }
Write-Host "Scene:              $($Build.level_asset)"
Write-Host "Skeletal actors:    $SkeletalCount"
Write-Host "Animation sections: $AnimationSections"
Write-Host "Evaluated contacts: $($Combat.attack_count)"
Write-Host "Terminal actors:    $($Death.terminal_count)"
Write-Host "Dungeon modules:    $($Environment.module_count)"
Write-Host "Dungeon props:      $($Environment.prop_count)"
Write-Host "Dungeon lights:     $($Environment.light_count)"
Write-Host "Camera clearance:   $([math]::Round([double]$Environment.camera_obstruction_checks.minimum_camera_clearance_cm, 2)) cm"
if ([int]$Death.terminal_count -eq 0) { Write-Warning "Current fixture contains no death/defeat event; terminal policy loaded but corpse persistence is not visually exercised in this render." }

Write-Host ""
if ($SkipRender) { & $ContinueScript -UnrealEditorCmd $UnrealEditorCmd -SkipRender }
else { & $ContinueScript -UnrealEditorCmd $UnrealEditorCmd }
if ($LASTEXITCODE -ne 0) { throw "Slice 28A continuation failed with exit code $LASTEXITCODE" }
