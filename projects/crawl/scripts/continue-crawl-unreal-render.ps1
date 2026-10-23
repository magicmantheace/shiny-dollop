param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$PresetScript = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\create_render_preset.py"
$Manifest = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\stage_manifest.json"
$AnimationPlan = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\animation_plan.json"
$UnrealResult = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\unreal_build_result.json"

if (-not (Test-Path $UnrealEditorCmd)) {
    throw "UnrealEditor-Cmd.exe not found at $UnrealEditorCmd"
}
if (-not (Test-Path $Manifest)) {
    throw "Staging manifest missing at $Manifest. Run the vertical-slice pipeline first."
}
if (-not (Test-Path $AnimationPlan)) {
    throw "Animation plan missing at $AnimationPlan. Run the vertical-slice pipeline first."
}
if (-not (Test-Path $UnrealResult)) {
    throw "Unreal build metadata missing at $UnrealResult. The scene build did not complete."
}

$ManifestData = Get-Content $Manifest -Raw | ConvertFrom-Json
$AnimationData = Get-Content $AnimationPlan -Raw | ConvertFrom-Json
$Build = Get-Content $UnrealResult -Raw | ConvertFrom-Json

if (-not $Build.level_asset -or -not $Build.sequence_asset) {
    throw "Unreal build metadata is incomplete: level_asset/sequence_asset missing."
}
if ($Build.manifest_digest -ne $ManifestData.digest) {
    throw "Generated Unreal scene does not match the current staging manifest digest."
}
if ($Build.animation_plan_digest -ne $AnimationData.digest) {
    throw "Generated Unreal scene does not match the current animation plan digest."
}

$SkeletalCount = @($Build.presentation_assets.skeletal_actor_ids).Count
$FallbackCount = @($Build.presentation_assets.fallback_actor_ids).Count
$AnimationSections = [int]$Build.presentation_assets.animation_section_count

Write-Host "== Existing Unreal scene validated =="
Write-Host "Generated map:      $($Build.level_asset)"
Write-Host "Generated sequence: $($Build.sequence_asset)"
Write-Host "Skeletal actors:    $SkeletalCount"
Write-Host "Fallback actors:    $FallbackCount"
Write-Host "Animation sections: $AnimationSections"

if ($SkeletalCount -lt 1) {
    throw "The generated scene contains no skeletal actors. Do not continue as a skeletal presentation validation."
}
if ($AnimationSections -lt 1) {
    throw "The generated scene contains no bound skeletal animation sections."
}

Write-Host ""
Write-Host "== Build Movie Render Queue H.264 preset =="
& $UnrealEditorCmd $Project "-ExecutePythonScript=$PresetScript" -unattended -nop4 -nosplash -log
$PresetExit = $LASTEXITCODE

if (-not (Test-Path $UnrealResult)) {
    throw "Render-preset run produced no build metadata. Unreal exit code: $PresetExit"
}

$Build = Get-Content $UnrealResult -Raw | ConvertFrom-Json
if (-not $Build.render_config_object -or -not $Build.sequence_object -or -not $Build.render_output_directory) {
    throw "Render-preset metadata is incomplete. Unreal exit code: $PresetExit"
}
if ($PresetExit -ne 0) {
    Write-Warning "Unreal returned exit code $PresetExit after writing valid render-preset metadata. Continuing because the generated artifacts validate successfully."
}

Write-Host "Render preset:      $($Build.render_config_object)"
Write-Host "Render output:      $($Build.render_output_directory)"

if ($SkipRender) {
    Write-Host ""
    Write-Host "UNREAL SKELETAL SCENE PASS - scene, animation bindings, and render preset are valid. Rendering skipped."
    exit 0
}

Write-Host ""
Write-Host "== Render skeletal Crawl footage =="
$RenderStartedUtc = [DateTime]::UtcNow
& $UnrealEditorCmd `
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
$RenderExit = $LASTEXITCODE

$RenderedVideo = Get-ChildItem -Path $Build.render_output_directory -Filter "*.mp4" -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1

if (-not $RenderedVideo) {
    throw "Movie render produced no MP4 under $($Build.render_output_directory). Unreal exit code: $RenderExit"
}
if ($RenderedVideo.LastWriteTimeUtc -lt $RenderStartedUtc.AddSeconds(-1)) {
    throw "Movie render left only a stale MP4 at $($RenderedVideo.FullName). Unreal exit code: $RenderExit"
}
if ($RenderExit -ne 0) {
    Write-Warning "Unreal returned exit code $RenderExit but a rendered MP4 exists. Treating the artifact, not shutdown status, as the render acceptance signal."
}

Write-Host ""
Write-Host "OVERALL PASS - Crawl skeletal presentation footage completed locally."
Write-Host "Skeletal actors:    $SkeletalCount"
Write-Host "Animation sections: $AnimationSections"
Write-Host "Video: $($RenderedVideo.FullName)"
