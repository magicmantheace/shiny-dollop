param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RepoParent = Split-Path -Parent $RepoRoot
$MediaHome = if ($env:UNDERREACH_MEDIA_HOME) { $env:UNDERREACH_MEDIA_HOME } else { Join-Path $RepoParent "CrawlMedia" }
$ComfyHome = Join-Path $MediaHome "ComfyUI"
$CheckpointDir = Join-Path $ComfyHome "models\checkpoints"
$MediaVenv = Join-Path $MediaHome "python\.venv"
$HfExe = Join-Path $MediaVenv "Scripts\hf.exe"
if (-not (Test-Path $HfExe)) {
    $HfExe = Join-Path $MediaVenv "Scripts\huggingface-cli.exe"
}

$RepoId = "RunDiffusion/Juggernaut-XL-v9"
$FileName = "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
$ExpectedSha256 = "c9e3e68f89b8e38689e1097d4be4573cf308de4e3fd044c64ca697bdb4aa8bca"
$Destination = Join-Path $CheckpointDir $FileName
$StageDir = Join-Path $MediaHome "hf-stage\juggernaut-xl-v9"

Write-Host "UNDERREACH CINEMATIC IMAGE MODEL" -ForegroundColor Cyan
Write-Host "Model: $RepoId"
Write-Host "Checkpoint: $FileName"
Write-Host "Destination: $Destination"
Write-Host ""

if (-not (Test-Path $HfExe)) {
    throw "Hugging Face CLI was not found at $MediaVenv. Run install-underreach-media-pipeline.bat first."
}
if (-not (Test-Path $ComfyHome)) {
    throw "ComfyUI was not found at $ComfyHome. Run install-underreach-media-pipeline.bat first."
}
New-Item -ItemType Directory -Force -Path $CheckpointDir, $StageDir | Out-Null

if (Test-Path $Destination) {
    $ExistingHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash.ToLowerInvariant()
    if ($ExistingHash -eq $ExpectedSha256) {
        Write-Host "[OK] Juggernaut XL v9 is already installed and hash-verified." -ForegroundColor Green
        exit 0
    }
    Write-Warning "Existing checkpoint hash does not match. Removing the invalid file before download."
    Remove-Item -Force -LiteralPath $Destination
}

Write-Host "[STEP] Downloading Juggernaut XL v9 (~7.1 GB) from Hugging Face..."
# Current hf CLI rejects combining --local-dir and --cache-dir. HF_HOME already
# provides shared cache configuration for the media environment, so this one-off
# staged download uses --local-dir only. The CLI can resume partial staged files.
& $HfExe download $RepoId $FileName --local-dir $StageDir
if ($LASTEXITCODE -ne 0) {
    throw "Hugging Face download failed with exit code $LASTEXITCODE."
}

$Downloaded = Join-Path $StageDir $FileName
if (-not (Test-Path $Downloaded)) {
    throw "Download completed but checkpoint was not found at $Downloaded."
}
$DownloadedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Downloaded).Hash.ToLowerInvariant()
if ($DownloadedHash -ne $ExpectedSha256) {
    throw "Juggernaut checkpoint SHA256 mismatch. Expected $ExpectedSha256, got $DownloadedHash."
}

Copy-Item -Force -LiteralPath $Downloaded -Destination $Destination
$FinalHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash.ToLowerInvariant()
if ($FinalHash -ne $ExpectedSha256) {
    throw "Installed Juggernaut checkpoint failed final SHA256 verification."
}

Write-Host ""
Write-Host "[OK] Cinematic checkpoint installed and verified." -ForegroundColor Green
Write-Host "Alpha will use it automatically while UNDERREACH_ALPHA_VIEWER_FACING=true."
Write-Host "The generic/non-Alpha provider configuration remains unchanged."
Write-Host ""
Write-Host "Model license/use terms are controlled by the upstream RunDiffusion/Juggernaut-XL-v9 model card."
