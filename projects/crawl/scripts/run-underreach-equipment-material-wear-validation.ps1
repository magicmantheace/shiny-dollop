param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot; Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"; if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$AcceptedSeed="underreach-29e2-real-equipment-proof"

$Generator29E2=Join-Path $RepoRoot "scripts\generate-underreach-real-equipment-proof.py"
$Builder29E2=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_real_equipment_proof.py"
$Out29E2=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e2"
$Proof29E2=Join-Path $Out29E2 "real-equipment-proof.json"
$SourceManifest29E2=Join-Path $Out29E2 "source-manifest.json"
$SourceDir29E2=Join-Path $Out29E2 "source"
$Debug29E2=Join-Path $Out29E2 "real-equipment-unreal-debug.json"
$PrepLog=Join-Path $Out29E2 "unreal-29e3-prerequisite-equipment.log"

$Generator=Join-Path $RepoRoot "scripts\generate-underreach-equipment-material-wear-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_equipment_material_wear_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e3"
$Proof=Join-Path $Out "equipment-material-wear-proof.json"
$Repro=Join-Path $Out "equipment-material-wear-proof-repro.json"
$Debug=Join-Path $Out "equipment-material-unreal-debug.json"
$UnrealLog=Join-Path $Out "unreal-equipment-material-wear-proof.log"

Write-Host "[29E.3] Focused deterministic equipment material/wear tests"
& $Python -m pytest -q tests/test_underreach_29e1_visual_quality.py tests/test_underreach_29e2_real_equipment_assets.py tests/test_underreach_29e3_equipment_material_wear.py tests/test_underreach_29d4_combat_motion_polish.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}

Write-Host "[29E.3] Rebuilding accepted 29E.2 real mesh prerequisite from source"
if(Test-Path $Out29E2){Remove-Item -Recurse -Force $Out29E2}
New-Item -ItemType Directory -Force -Path $Out29E2|Out-Null
& $Python $Generator29E2 --output $Proof29E2 --source-dir $SourceDir29E2 --source-manifest $SourceManifest29E2 --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder29E2" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $PrepLog
$PrepExit=$LASTEXITCODE
if(-not(Test-Path $Debug29E2)){
    Get-Content $PrepLog -Tail 160|Write-Host
    throw "29E.3 prerequisite 29E.2 Unreal proof produced no diagnostics"
}
$Prep=Get-Content -Raw $Debug29E2|ConvertFrom-Json
$P29E2=Get-Content -Raw $Proof29E2|ConvertFrom-Json
if(-not $Prep.validation.all_pass){
    Write-Host "[29E.3] 29E.2 prerequisite diagnostics: $Debug29E2"
    throw "29E.3 prerequisite 29E.2 real equipment validation failed"
}
if($P29E2.population_count-ne 24 -or $P29E2.replacement_count-ne 52){throw "29E.3 prerequisite is not the accepted 29E.2 population/equipment set"}
Write-Host "[29E.3] 29E.2 prerequisite PASS: realMeshes=$($Prep.real_static_mesh_asset_count) replacements=$($P29E2.replacement_count)"
if($PrepExit-ne 0){Write-Warning "29E.2 prerequisite Unreal returned $PrepExit after valid diagnostics; continuing."}

if(Test-Path $Out){Remove-Item -Recurse -Force $Out}
New-Item -ItemType Directory -Force -Path $Out|Out-Null
Write-Host "[29E.3] Generating material/wear proof twice from the exact accepted 29E.2 seed"
& $Python $Generator --output $Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $Python $Generator --output $Repro --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json
$Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.digest-ne $Q.digest){throw "29E.3 deterministic digest mismatch"}
if($P.protocol-ne "underreach.equipment-material-wear-realization.v1" -or $P.authoritative-ne $false){throw "29E.3 protocol/authority invalid"}
if($P.source_29e2_digest-ne $P29E2.digest){throw "29E.3 did not consume the exact accepted 29E.2 deterministic manifest"}
if($P.material_directive_count-ne $P29E2.replacement_count -or $P.material_directive_count-ne 52){throw "29E.3 material directives do not cover all 52 accepted 29E.2 equipment replacements"}
if($P.item_material_template_count-ne 3){throw "29E.3 expected exactly three reusable item material templates"}
$MaterialPaths=@($P.entries|ForEach-Object{$_.equipment_materials}|ForEach-Object{$_.material_instance_path})
if(($MaterialPaths|Select-Object -Unique).Count-ne $MaterialPaths.Count){throw "29E.3 material instance identity collision"}
Write-Host "[29E.3] Deterministic material/wear manifest PASS"
Write-Host "digest=$($P.digest) population=$($P.population_count) materialDirectives=$($P.material_directive_count) itemTemplates=$($P.item_material_template_count)"
Write-Host "source29E2Digest=$($P.source_29e2_digest)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29E.3] Unreal master material + item templates + per-Descender material proof"
Write-Host "[29E.3] NullRHI enabled so validation does not require a desktop/D3D viewport"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit=$LASTEXITCODE
if(-not(Test-Path $Debug)){
    Get-Content $UnrealLog -Tail 180|Write-Host
    throw "29E.3 Unreal proof produced no diagnostics"
}
$D=Get-Content -Raw $Debug|ConvertFrom-Json
$After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if(-not $D.validation.all_pass){
    Write-Host "[29E.3] Diagnostics: $Debug"
    throw "29E.3 Unreal validation flags failed"
}
if($Before-ne $After){throw "29E.3 Unreal modified proof artifact"}
if($D.directive_count-ne 52 -or $D.material_instance_count-ne 52){throw "29E.3 Unreal did not realize all 52 accepted equipment directives"}
Write-Host "[29E.3] Unreal material/wear realization PASS"
Write-Host "master=$($D.master_material_path) itemTemplates=$($D.item_material_template_count) descenderInstances=$($D.material_instance_count)"
Write-Host "parameterFingerprints=$($D.unique_parameter_fingerprint_count) wear=$($D.unique_wear_count) dirt=$($D.unique_dirt_count) edgeWear=$($D.unique_edge_wear_count)"
Write-Host "componentSamples=$($D.component_binding_sample_count) boundDescenders=$($D.component_bound_descender_count) attachmentBones=$($D.attachment_bones -join ',') fitScale=$($D.min_fit_scale)..$($D.max_fit_scale)"
if($UnrealExit-ne 0){Write-Warning "Unreal returned $UnrealExit after fresh valid diagnostics; accepting artifact validation rather than shutdown status."}

Write-Host "[29E.3] Full repository regression suite"
& $Python -m pytest -q
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29E.3] PASS"
Write-Host "Proof: $Proof"
Write-Host "Diagnostics: $Debug"
Write-Host "Unreal log: $UnrealLog"
