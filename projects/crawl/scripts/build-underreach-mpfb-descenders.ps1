param(
    [string]$Blender = "D:\Blender\blender.exe",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\29a1"
}
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Input = Join-Path $OutputDirectory "character_authoring_inputs.json"
$Script = Join-Path $RepoRoot "tools\character_pipeline\generate_mpfb_descenders.py"
$Manifest = Join-Path $OutputDirectory "blender_character_export_manifest.json"
foreach ($Required in @($Blender, $Python, $Script)) {
    if (-not (Test-Path $Required)) { throw "Required 29A.1 input is missing: $Required" }
}
& $Python (Join-Path $PSScriptRoot "generate-underreach-character-dna.py") --output $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Character DNA generation failed." }
$StartedUtc = [DateTime]::UtcNow
& $Blender --background --python $Script -- $Input $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "MPFB character authoring failed." }
if (-not (Test-Path $Manifest)) { throw "Blender did not emit the required character manifest." }
$ManifestItem = Get-Item $Manifest
if ($ManifestItem.LastWriteTimeUtc -lt $StartedUtc) {
    throw "Blender left a stale character manifest; inspect the Python traceback above."
}
Write-Host "UNDERREACH 29A.1 MPFB EXPORT PASS"
Write-Host "Manifest: $Manifest"
