param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot; Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"; if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generator=Join-Path $RepoRoot "scripts\generate-underreach-real-equipment-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_real_equipment_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e2"; New-Item -ItemType Directory -Force -Path $Out|Out-Null
$Proof=Join-Path $Out "real-equipment-proof.json"
$Repro=Join-Path $Out "real-equipment-proof-repro.json"
$SourceManifest=Join-Path $Out "source-manifest.json"
$SourceDir=Join-Path $Out "source"
$Debug=Join-Path $Out "real-equipment-unreal-debug.json"
$UnrealLog=Join-Path $Out "unreal-real-equipment-proof.log"

Write-Host "[29E.2] Focused real equipment asset integration tests"
& $Python -m pytest -q tests/test_underreach_29a1_1.py tests/test_underreach_29a2_population.py tests/test_underreach_29d4_combat_motion_polish.py tests/test_underreach_29e1_visual_quality.py tests/test_underreach_29e2_real_equipment_assets.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}

if(Test-Path $Out){Remove-Item -Recurse -Force $Out}
New-Item -ItemType Directory -Force -Path $Out|Out-Null

Write-Host "[29E.2] Generating real mesh sources and integration proof twice for reproducibility"
& $Python $Generator --output $Proof --source-dir $SourceDir --source-manifest $SourceManifest --seed "underreach-29e2-real-equipment-proof" --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$SourceHashesBefore=@{}
Get-ChildItem $SourceDir -Filter *.obj | Sort-Object Name | ForEach-Object {$SourceHashesBefore[$_.Name]=(Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLowerInvariant()}

& $Python $Generator --output $Repro --source-dir $SourceDir --source-manifest $SourceManifest --seed "underreach-29e2-real-equipment-proof" --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json; $Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.digest-ne $Q.digest){throw "29E.2 deterministic proof digest mismatch"}
if($P.protocol-ne "underreach.real-equipment-asset-integration.v1" -or $P.authoritative-ne $false){throw "29E.2 protocol/authority invalid"}
if($P.unique_real_mesh_asset_count-ne 3 -or $P.unique_material_instance_count-ne 3){throw "29E.2 expected exactly three real mesh/material candidates"}
if($P.replacement_count-le 0){throw "29E.2 produced no equipment replacements"}
foreach($File in Get-ChildItem $SourceDir -Filter *.obj){
    $After=(Get-FileHash -Algorithm SHA256 $File.FullName).Hash.ToLowerInvariant()
    if($SourceHashesBefore[$File.Name]-ne $After){throw "29E.2 source mesh changed across deterministic regeneration: $($File.Name)"}
}
$SourceRecords=@((Get-Content -Raw $SourceManifest|ConvertFrom-Json).records)
if($SourceRecords.Count-ne 3){throw "29E.2 source manifest does not contain exactly three assets"}
Write-Host "[29E.2] Deterministic source/integration proof PASS"
Write-Host "digest=$($P.digest) population=$($P.population_count) replacements=$($P.replacement_count) sources=$($SourceRecords.Count)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29E.2] Unreal import + material-instance consumer proof"
Write-Host "[29E.2] NullRHI enabled so validation does not require a desktop/D3D viewport"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit=$LASTEXITCODE
if(-not(Test-Path $Debug)){Get-Content $UnrealLog -Tail 160|Write-Host; throw "29E.2 Unreal proof produced no diagnostics"}
$D=Get-Content -Raw $Debug|ConvertFrom-Json
$After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if(-not $D.validation.all_pass){throw "29E.2 Unreal validation flags failed"}
if($Before-ne $After){throw "29E.2 Unreal modified proof artifact"}
Write-Host "[29E.2] Unreal real equipment integration PASS"
Write-Host "realMeshes=$($D.real_static_mesh_asset_count) materialInstances=$($D.material_instance_count) directives=$($D.equipment_directive_count)"
Write-Host "fitScale=$($D.min_fit_scale)..$($D.max_fit_scale) attachmentBones=$($D.attachment_bones -join ',')"
if($UnrealExit-ne 0){Write-Warning "Unreal returned $UnrealExit after fresh valid diagnostics; accepting artifact validation rather than shutdown status."}

Write-Host "[29E.2] Full repository regression suite"
& $Python -m pytest -q
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29E.2] PASS"
Write-Host "Proof: $Proof"
Write-Host "Source manifest: $SourceManifest"
Write-Host "Diagnostics: $Debug"
Write-Host "Unreal log: $UnrealLog"
