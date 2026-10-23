param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [string]$Seed = "crawl-v09-death-persistence",
    [int]$Crawlers = 12,
    [int]$Floors = 2,
    [int]$MaxSteps = 5000,
    [int]$MaxActors = 8,
    [double]$PostRollSeconds = 3.0,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Manifest = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\stage_manifest.json"
$AnimationPlan = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\animation_plan.json"
$AssetRegistry = Join-Path $RepoRoot "unreal\CrawlPresentation\presentation_assets.json"
$Report = Join-Path $RepoRoot "validation\crawl-v0.9-death-persistence.json"
$DeathDebug = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\death_debug.json"
$RenderRunner = Join-Path $RepoRoot "scripts\run-crawl-camera-safe-render.ps1"

foreach ($required in @($Python, $UnrealEditorCmd, $RenderRunner)) {
    if (-not (Test-Path $required)) { throw "Required death-persistence input missing: $required" }
}

Write-Host "== Export canonical terminal combat encounter =="
& $Python -m livingworld.crawl_unreal_vertical_demo `
    --seed $Seed `
    --crawlers $Crawlers `
    --floors $Floors `
    --max-steps $MaxSteps `
    --max-actors $MaxActors `
    --require-terminal `
    --post-roll-seconds $PostRollSeconds `
    --output "validation/crawl-v0.9-death-persistence.json" `
    --manifest "unreal/CrawlPresentation/Generated/stage_manifest.json" `
    --animation-plan "unreal/CrawlPresentation/Generated/animation_plan.json"
if ($LASTEXITCODE -ne 0) { throw "Canonical terminal encounter export failed with exit code $LASTEXITCODE" }

if (-not (Test-Path $Report)) { throw "Death-persistence validation report missing: $Report" }
$Export = Get-Content $Report -Raw | ConvertFrom-Json
if (-not [bool]$Export.require_terminal -or [int]$Export.terminal_event_count -lt 1) {
    throw "Export did not contain a canonical terminal event."
}
if (-not [bool]$Export.overall) { throw "Canonical death-persistence export checks did not pass." }

$ManifestData = Get-Content $Manifest -Raw | ConvertFrom-Json
$AnimationData = Get-Content $AnimationPlan -Raw | ConvertFrom-Json
$RegistryData = Get-Content $AssetRegistry -Raw | ConvertFrom-Json
$TerminalBeats = @($ManifestData.beats | Where-Object { $_.action -in @("death", "defeat") })
$TerminalIntents = @($AnimationData.intents | Where-Object { $_.role -in @("death", "defeat") })
if ($TerminalBeats.Count -lt 1) { throw "Staging manifest contains no canonical death/defeat beat." }
if ($TerminalIntents.Count -lt 1) { throw "Animation plan contains no terminal death/defeat intent." }
$StagedActorIds = @($ManifestData.actors | ForEach-Object { $_.actor_id })
foreach ($Intent in $TerminalIntents) {
    if ($Intent.actor_id -notin $StagedActorIds) { throw "Terminal actor is not staged: $($Intent.actor_id)" }
    $SlotProperty = $RegistryData.slots.PSObject.Properties[$Intent.asset_slot]
    if ($null -eq $SlotProperty -or [string]::IsNullOrWhiteSpace([string]$SlotProperty.Value)) {
        throw "Terminal animation slot is unresolved before Unreal: $($Intent.asset_slot)"
    }
}
$LatestTerminalStart = ($TerminalIntents | Measure-Object start_seconds -Maximum).Maximum
if ([double]$ManifestData.duration_seconds - [double]$LatestTerminalStart -lt 3.0) {
    throw "Terminal fixture does not leave three seconds of presentation after death starts."
}

Write-Host "Terminal events:    $($Export.terminal_event_count)"
Write-Host "Terminal actions:   $($Export.terminal_actions -join ', ')"
Write-Host "Presentation tail:  $PostRollSeconds s"
Write-Host ""
Write-Host "== Build, validate corpse persistence, and render =="
if ($SkipRender) {
    & $RenderRunner -UnrealEditorCmd $UnrealEditorCmd -SkipRender
}
else {
    & $RenderRunner -UnrealEditorCmd $UnrealEditorCmd
}
if ($LASTEXITCODE -ne 0) { throw "Death-persistence render pipeline failed with exit code $LASTEXITCODE" }

if (-not (Test-Path $DeathDebug)) { throw "Death diagnostics were not produced: $DeathDebug" }
$Death = Get-Content $DeathDebug -Raw | ConvertFrom-Json
if ([int]$Death.terminal_count -lt 1) { throw "Rendered death fixture produced no terminal actor diagnostics." }
foreach ($Actor in @($Death.actors)) {
    if (-not [bool]$Actor.persistent) { throw "Corpse persistence failed for $($Actor.actor_id)." }
    if ([double]$Actor.maximum_bone_delta_cm -gt 2.0) {
        throw "Corpse drift exceeded tolerance for $($Actor.actor_id): $($Actor.maximum_bone_delta_cm) cm"
    }
    if (@($Actor.samples).Count -lt 4) { throw "Corpse validator did not sample enough post-death times for $($Actor.actor_id)." }
    if ([double]$Actor.corpse_hold_duration_seconds -lt 2.0) { throw "Corpse hold is too short for $($Actor.actor_id)." }
    if (-not [bool]$Actor.transform_stable) { throw "Terminal actor transform moved after death: $($Actor.actor_id)." }
    if (-not [bool]$Actor.orientation_stable) { throw "Terminal corpse orientation changed: $($Actor.actor_id)." }
}

Write-Host ""
Write-Host "DEATH PERSISTENCE PASS"
Write-Host "Terminal actors:    $($Death.terminal_count)"
foreach ($Actor in @($Death.actors)) {
    Write-Host ("  {0}: max corpse drift={1:N3} cm persistent={2}" -f $Actor.actor_id, [double]$Actor.maximum_bone_delta_cm, [bool]$Actor.persistent)
}
Write-Host "Report:             $Report"
Write-Host "Death diagnostics:  $DeathDebug"
Write-Host "Manifest:           $Manifest"
Write-Host "Animation plan:     $AnimationPlan"
