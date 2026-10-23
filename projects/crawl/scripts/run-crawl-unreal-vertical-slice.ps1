param(
    [int]$Crawlers = 12,
    [int]$Floors = 2,
    [int]$MaxSteps = 5000,
    [int]$MaxActors = 8,
    [string]$UnrealEditorCmd = "",
    [switch]$SkipFullRegression,
    [switch]$SkipUnreal,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create/activate the repo venv first."
}

$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$BuildScript = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_vertical_slice.py"
$PresetScript = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\create_render_preset.py"
$Manifest = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\stage_manifest.json"
$AnimationPlan = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\animation_plan.json"
$AssetRegistry = Join-Path $RepoRoot "unreal\CrawlPresentation\presentation_assets.json"
$UnrealResult = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\unreal_build_result.json"
$ValidationReport = Join-Path $RepoRoot "validation\crawl-v0.9-unreal-vertical-slice.json"

function Get-UnrealCandidate {
    param(
        [string]$InstallRoot,
        [string]$Source
    )

    if (-not $InstallRoot) { return $null }
    $expanded = [Environment]::ExpandEnvironmentVariables($InstallRoot.Trim('"'))
    $candidate = Join-Path $expanded "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
    if (-not (Test-Path $candidate)) { return $null }

    $version = ""
    $leaf = Split-Path $expanded -Leaf
    if ($leaf -match '^UE_(.+)$') { $version = $Matches[1] }

    [PSCustomObject]@{
        Path = (Resolve-Path $candidate).Path
        Root = (Resolve-Path $expanded).Path
        VersionText = $version
        Source = $Source
        Updated = (Get-Item $candidate).LastWriteTimeUtc
    }
}

function Get-EpicLauncherCandidates {
    $manifestPaths = @(
        (Join-Path $env:ProgramData "Epic\UnrealEngineLauncher\LauncherInstalled.dat"),
        (Join-Path $env:ProgramData "Epic\EpicGamesLauncher\Data\Manifests\LauncherInstalled.dat")
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($manifestPath in $manifestPaths) {
        try {
            $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
            foreach ($entry in @($manifest.InstallationList)) {
                if (-not $entry.InstallLocation) { continue }
                if ($entry.AppName -and $entry.AppName -notmatch '^UE_' -and $entry.ArtifactId -and $entry.ArtifactId -notmatch '^UE_') { continue }
                $candidate = Get-UnrealCandidate -InstallRoot $entry.InstallLocation -Source "Epic Launcher manifest: $manifestPath"
                if ($candidate) { $candidate }
            }
        }
        catch {
            Write-Verbose "Could not parse Epic Launcher manifest $manifestPath : $($_.Exception.Message)"
        }
    }
}

function Get-RegistryCandidates {
    $registryRoots = @(
        "HKLM:\SOFTWARE\EpicGames\Unreal Engine",
        "HKLM:\SOFTWARE\WOW6432Node\EpicGames\Unreal Engine",
        "HKCU:\SOFTWARE\Epic Games\Unreal Engine\Builds"
    )

    foreach ($registryRoot in $registryRoots) {
        if (-not (Test-Path $registryRoot)) { continue }
        try {
            if ($registryRoot -like '*\Builds') {
                $props = Get-ItemProperty $registryRoot
                foreach ($property in $props.PSObject.Properties) {
                    if ($property.Name -match '^PS') { continue }
                    if ($property.Value -isnot [string]) { continue }
                    $candidate = Get-UnrealCandidate -InstallRoot $property.Value -Source "Registry: $registryRoot"
                    if ($candidate) { $candidate }
                }
            }
            else {
                Get-ChildItem $registryRoot -ErrorAction SilentlyContinue | ForEach-Object {
                    $props = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
                    foreach ($propertyName in @("InstalledDirectory", "InstallLocation")) {
                        $value = $props.$propertyName
                        if ($value) {
                            $candidate = Get-UnrealCandidate -InstallRoot $value -Source "Registry: $($_.Name)"
                            if ($candidate) { $candidate }
                        }
                    }
                }
            }
        }
        catch {
            Write-Verbose "Could not inspect Unreal registry root $registryRoot : $($_.Exception.Message)"
        }
    }
}

function Resolve-UnrealEditorCmd {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        if (-not (Test-Path $ExplicitPath)) {
            throw "UnrealEditor-Cmd.exe was not found at the supplied path: $ExplicitPath"
        }
        return (Resolve-Path $ExplicitPath).Path
    }

    $envRoots = @($env:UNREAL_ENGINE_ROOT, $env:UE_ROOT) | Where-Object { $_ }
    foreach ($root in $envRoots) {
        $candidate = Get-UnrealCandidate -InstallRoot $root -Source "environment variable"
        if ($candidate) { return $candidate.Path }
    }

    $candidates = @()
    $candidates += @(Get-EpicLauncherCandidates)
    $candidates += @(Get-RegistryCandidates)

    $roots = @(
        "C:\Program Files\Epic Games",
        "C:\Epic Games",
        "D:\Program Files\Epic Games",
        "D:\Epic Games",
        "E:\Program Files\Epic Games",
        "E:\Epic Games",
        "F:\Program Files\Epic Games",
        "F:\Epic Games"
    ) | Where-Object { Test-Path $_ }

    foreach ($root in $roots) {
        Get-ChildItem -Path $root -Directory -Filter "UE_*" -ErrorAction SilentlyContinue | ForEach-Object {
            $candidate = Get-UnrealCandidate -InstallRoot $_.FullName -Source "filesystem scan"
            if ($candidate) { $candidates += $candidate }
        }
    }

    $selected = $candidates |
        Group-Object Path |
        ForEach-Object { $_.Group | Select-Object -First 1 } |
        Sort-Object @{ Expression = {
            try { [version]($_.VersionText -replace '[^0-9\.]','') }
            catch { [version]'0.0' }
        }; Descending = $true }, @{ Expression = 'Updated'; Descending = $true } |
        Select-Object -First 1

    if (-not $selected) {
        throw @"
Could not locate UnrealEditor-Cmd.exe automatically.
The script checked:
  -UNREAL_ENGINE_ROOT / UE_ROOT
  -Epic Games LauncherInstalled.dat
  -Windows Unreal Engine registry entries
  -common Epic Games install folders on C:-F:

If Unreal Engine is installed, find the executable with:
  Get-ChildItem C:\,D:\,E:\,F:\ -Filter UnrealEditor-Cmd.exe -File -Recurse -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName

Then rerun with:
  -UnrealEditorCmd "<full path to UnrealEditor-Cmd.exe>"
"@
    }

    Write-Host "Detected Unreal Engine from $($selected.Source): $($selected.Path)"
    return $selected.Path
}

Write-Host "== Crawl v0.9 Unreal presentation focused tests =="
& $Python -m pytest tests/test_presentation_animation.py tests/test_crawl_unreal_vertical_slice.py -q
if ($LASTEXITCODE -ne 0) { throw "Unreal presentation tests failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "== Export a real autonomous Crawl combat encounter =="
& $Python -m livingworld.crawl_unreal_vertical_demo `
    --seed "crawl-v09-unreal-validation" `
    --crawlers $Crawlers `
    --floors $Floors `
    --max-steps $MaxSteps `
    --max-actors $MaxActors `
    --output "validation/crawl-v0.9-unreal-vertical-slice.json" `
    --manifest "unreal/CrawlPresentation/Generated/stage_manifest.json" `
    --animation-plan "unreal/CrawlPresentation/Generated/animation_plan.json"
if ($LASTEXITCODE -ne 0) { throw "Canonical presentation export failed with exit code $LASTEXITCODE." }
if (-not (Test-Path $Manifest)) { throw "Staging manifest was not created at $Manifest." }
if (-not (Test-Path $AnimationPlan)) { throw "Animation plan was not created at $AnimationPlan." }

if (-not $SkipFullRegression) {
    Write-Host ""
    Write-Host "== Full inherited repository regression suite =="
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Full regression suite failed with exit code $LASTEXITCODE." }
}

if ($SkipUnreal) {
    Write-Host ""
    Write-Host "BACKEND PASS - Canonical staging and semantic animation plans created. Unreal execution was skipped."
    Write-Host "Report: validation\crawl-v0.9-unreal-vertical-slice.json"
    Write-Host "Manifest: unreal\CrawlPresentation\Generated\stage_manifest.json"
    Write-Host "Animation: unreal\CrawlPresentation\Generated\animation_plan.json"
    exit 0
}

$Unreal = Resolve-UnrealEditorCmd -ExplicitPath $UnrealEditorCmd
Write-Host ""
Write-Host "== Unreal Editor =="
Write-Host $Unreal

$env:CRAWL_STAGE_MANIFEST = (Resolve-Path $Manifest).Path
$env:CRAWL_ANIMATION_PLAN = (Resolve-Path $AnimationPlan).Path
if (Test-Path $AssetRegistry) {
    $env:CRAWL_PRESENTATION_ASSETS = (Resolve-Path $AssetRegistry).Path
    Write-Host "Presentation asset registry: $env:CRAWL_PRESENTATION_ASSETS"
}
else {
    Remove-Item Env:CRAWL_PRESENTATION_ASSETS -ErrorAction SilentlyContinue
    Write-Host "No presentation_assets.json found; Unreal will use primitive fallback actors."
}

Write-Host ""
Write-Host "== Build deterministic procedural 3D scene and Level Sequence =="
& $Unreal $Project "-ExecutePythonScript=$BuildScript" -unattended -nop4 -nosplash -log
if ($LASTEXITCODE -ne 0) { throw "Unreal scene build failed with exit code $LASTEXITCODE." }
if (-not (Test-Path $UnrealResult)) { throw "Unreal did not create build metadata at $UnrealResult." }

Write-Host ""
Write-Host "== Build Movie Render Queue H.264 preset =="
& $Unreal $Project "-ExecutePythonScript=$PresetScript" -unattended -nop4 -nosplash -log
if ($LASTEXITCODE -ne 0) { throw "Unreal render-preset build failed with exit code $LASTEXITCODE." }

$Build = Get-Content $UnrealResult -Raw | ConvertFrom-Json
if (-not $Build.level_asset -or -not $Build.sequence_object -or -not $Build.render_config_object) {
    throw "Unreal build metadata is incomplete. Expected level_asset, sequence_object, and render_config_object."
}

Write-Host "Generated map:      $($Build.level_asset)"
Write-Host "Generated sequence: $($Build.sequence_object)"
Write-Host "Render preset:      $($Build.render_config_object)"
Write-Host "Render output:      $($Build.render_output_directory)"
if ($Build.presentation_assets) {
    Write-Host "Skeletal actors:    $(@($Build.presentation_assets.skeletal_actor_ids).Count)"
    Write-Host "Fallback actors:    $(@($Build.presentation_assets.fallback_actor_ids).Count)"
    Write-Host "Animation sections: $($Build.presentation_assets.animation_section_count)"
}

if ($SkipRender) {
    Write-Host ""
    Write-Host "UNREAL SCENE PASS - 3D scene and render preset were generated. Movie rendering was skipped."
    Write-Host "Open the project and load: $($Build.level_asset)"
    Write-Host "Sequence: $($Build.sequence_object)"
    exit 0
}

Write-Host ""
Write-Host "== Render first canonical Crawl footage with Movie Render Queue =="
& $Unreal `
    $Project `
    $Build.level_asset `
    -game `
    "-LevelSequence=$($Build.sequence_object)" `
    "-MoviePipelineConfig=$($Build.render_config_object)" `
    -windowed `
    "-resx=$($Build.render_width)" `
    "-resy=$($Build.render_height)" `
    -log `
    -notexturestreaming `
    -nop4
if ($LASTEXITCODE -ne 0) { throw "Movie Render Queue failed with exit code $LASTEXITCODE." }

$RenderedVideo = Get-ChildItem -Path $Build.render_output_directory -Filter "*.mp4" -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $RenderedVideo) {
    throw "Movie Render Queue completed but no MP4 was found under $($Build.render_output_directory). Check the Unreal log for encoder/plugin errors."
}

Write-Host ""
Write-Host "OVERALL PASS - Crawl v0.9 Unreal presentation vertical slice completed locally."
Write-Host "Report: validation\crawl-v0.9-unreal-vertical-slice.json"
Write-Host "Video: $($RenderedVideo.FullName)"
