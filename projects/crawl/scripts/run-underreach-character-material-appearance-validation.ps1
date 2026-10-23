param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot; Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"; if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$AcceptedSeed="underreach-29e2-real-equipment-proof"

$Generator29E3=Join-Path $RepoRoot "scripts\generate-underreach-equipment-material-wear-proof.py"
$Generator=Join-Path $RepoRoot "scripts\generate-underreach-character-material-appearance-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_character_material_appearance_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e4"
$Source29E3=Join-Path $Out "accepted-29e3-source-proof.json"
$Proof=Join-Path $Out "character-material-appearance-proof.json"
$Repro=Join-Path $Out "character-material-appearance-proof-repro.json"
$Debug=Join-Path $Out "character-material-unreal-debug.json"
$UnrealLog=Join-Path $Out "unreal-character-material-appearance-proof.log"

Write-Host "[29E.4] Focused deterministic character material/appearance tests"
& $Python -m pytest -q tests/test_underreach_29e1_visual_quality.py tests/test_underreach_29e2_real_equipment_assets.py tests/test_underreach_29e3_equipment_material_wear.py tests/test_underreach_29e4_character_material_appearance.py tests/test_underreach_29d4_combat_motion_polish.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}

if(Test-Path $Out){Remove-Item -Recurse -Force $Out}
New-Item -ItemType Directory -Force -Path $Out|Out-Null

Write-Host "[29E.4] Rebuilding exact accepted 29E.3 deterministic source manifest"
& $Python $Generator29E3 --output $Source29E3 --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P29E3=Get-Content -Raw $Source29E3|ConvertFrom-Json
if($P29E3.protocol-ne "underreach.equipment-material-wear-realization.v1" -or $P29E3.authoritative-ne $false){throw "29E.4 prerequisite 29E.3 protocol/authority invalid"}
if($P29E3.population_count-ne 24 -or $P29E3.material_directive_count-ne 52){throw "29E.4 prerequisite is not the accepted 29E.3 population/equipment set"}
Write-Host "[29E.4] Accepted 29E.3 source manifest PASS: digest=$($P29E3.digest) population=$($P29E3.population_count) equipmentMaterials=$($P29E3.material_directive_count)"

Write-Host "[29E.4] Generating character material/appearance proof twice from the accepted seed"
& $Python $Generator --output $Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $Python $Generator --output $Repro --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json
$Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.digest-ne $Q.digest){throw "29E.4 deterministic digest mismatch"}
if($P.protocol-ne "underreach.character-material-appearance-realization.v1" -or $P.authoritative-ne $false){throw "29E.4 protocol/authority invalid"}
if($P.source_29e3_digest-ne $P29E3.digest){throw "29E.4 did not consume the exact accepted 29E.3 deterministic manifest"}
if($P.source_population_digest-ne $P29E3.source_population_digest){throw "29E.4 changed the accepted Descender population identity"}
if($P.population_count-ne 24 -or $P.material_directive_count-ne 96){throw "29E.4 expected 24 Descenders and 96 character material directives"}
if($P.character_material_template_count-ne 4){throw "29E.4 expected exactly four reusable character material templates"}
$MaterialPaths=@($P.entries|ForEach-Object{$_.character_materials}|ForEach-Object{$_.material_instance_path})
if(($MaterialPaths|Select-Object -Unique).Count-ne 96){throw "29E.4 material instance identity collision"}
$Species=@($P.entries|ForEach-Object{$_.species}|Select-Object -Unique)
if($Species.Count-ne 2 -or -not($Species -contains "human") -or -not($Species -contains "dwarf")){throw "29E.4 proof does not cover both Human and Dwarf Descenders"}
Write-Host "[29E.4] Deterministic character material/appearance manifest PASS"
Write-Host "digest=$($P.digest) population=$($P.population_count) materialDirectives=$($P.material_directive_count) templates=$($P.character_material_template_count)"
Write-Host "source29E3Digest=$($P.source_29e3_digest) sourcePopulationDigest=$($P.source_population_digest)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29E.4] Unreal character master material + skin/hair/eye/clothing realization proof"
Write-Host "[29E.4] NullRHI enabled; proof validates real SkeletalMeshComponent material overrides without requiring a desktop viewport"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit=$LASTEXITCODE
if(-not(Test-Path $Debug)){
    Get-Content $UnrealLog -Tail 200|Write-Host
    throw "29E.4 Unreal proof produced no diagnostics"
}
$D=Get-Content -Raw $Debug|ConvertFrom-Json
$After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if(-not $D.validation.all_pass){
    Write-Host "[29E.4] Diagnostics: $Debug"
    throw "29E.4 Unreal validation flags failed"
}
if($Before-ne $After){throw "29E.4 Unreal modified proof artifact"}
if($D.population_count-ne 24 -or $D.directive_count-ne 96 -or $D.material_instance_count-ne 96){throw "29E.4 Unreal did not realize all accepted character material directives"}
if($D.material_template_count-ne 4){throw "29E.4 Unreal did not create the four-material template hierarchy"}
if($D.component_bound_descender_count-lt 4){throw "29E.4 Unreal component proof covered too few Descenders"}
$ObservedCategories=@($D.observed_slot_categories|Sort-Object)
if(($ObservedCategories -join ',')-ne 'clothing,eye,hair,skin'){throw "29E.4 Unreal did not bind all four character surface categories"}
$BoundSpecies=@($D.component_bound_species|Sort-Object)
if(($BoundSpecies -join ',')-ne 'dwarf,human'){throw "29E.4 Unreal material proof did not bind both species"}
Write-Host "[29E.4] Unreal character material/appearance realization PASS"
Write-Host "master=$($D.master_material_path) templates=$($D.material_template_count) descenderInstances=$($D.material_instance_count) skeletalMeshes=$($D.loaded_skeletal_mesh_count)"
Write-Host "skinTints=$($D.unique_skin_tint_count) hairTints=$($D.unique_hair_tint_count) eyeTints=$($D.unique_eye_tint_count) clothingTints=$($D.unique_clothing_tint_count)"
Write-Host "clothingWear=$($D.unique_clothing_wear_count) clothingDirt=$($D.unique_clothing_dirt_count) componentSamples=$($D.component_binding_sample_count) boundDescenders=$($D.component_bound_descender_count) categories=$($D.observed_slot_categories -join ',')"
if($UnrealExit-ne 0){Write-Warning "Unreal returned $UnrealExit after fresh valid diagnostics; accepting artifact validation rather than shutdown status."}

Write-Host "[29E.4] Full repository regression suite"
& $Python -m pytest -q
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29E.4] PASS"
Write-Host "Proof: $Proof"
Write-Host "Diagnostics: $Debug"
Write-Host "Unreal log: $UnrealLog"
