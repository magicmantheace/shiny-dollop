param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"
if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"

$E2Generator=Join-Path $RepoRoot "scripts\generate-underreach-real-equipment-proof.py"
$E2Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_real_equipment_proof.py"
$E2Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e2"
$E2Proof=Join-Path $E2Out "real-equipment-proof.json"
$E2SourceManifest=Join-Path $E2Out "source-manifest.json"
$E2SourceDir=Join-Path $E2Out "source"
$E2Debug=Join-Path $E2Out "real-equipment-unreal-debug.json"
$E2Log=Join-Path $E2Out "unreal-29e5-prerequisite-real-equipment.log"

$E3Generator=Join-Path $RepoRoot "scripts\generate-underreach-equipment-material-wear-proof.py"
$E3Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_equipment_material_wear_proof.py"
$E3Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e3"
$E3Proof=Join-Path $E3Out "equipment-material-wear-proof.json"
$E3Debug=Join-Path $E3Out "equipment-material-unreal-debug.json"
$E3Log=Join-Path $E3Out "unreal-29e5-prerequisite-equipment-material.log"

$Generator=Join-Path $RepoRoot "scripts\generate-underreach-equipment-character-combat-integration-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_equipment_character_combat_integration_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e5"
$Proof=Join-Path $Out "equipment-character-combat-integration-proof.json"
$Repro=Join-Path $Out "equipment-character-combat-integration-proof-repro.json"
$Debug=Join-Path $Out "equipment-character-combat-unreal-debug.json"
$UnrealLog=Join-Path $Out "unreal-equipment-character-combat-integration.log"

$Accepted29E2Digest="f5fc053be8f23b788321096e6141b88caaaa3f653868e3b0ecd244a62dc8d2f6"
$Accepted29E3Digest="a8ab58180e51a6ae6245daaff75d7cf625c5cfa1e44dd07e49cde00cb9bcaa79"
$Accepted29E4Digest="3614cedb01758a635e945bd506267d659aea120aad52fcf470f48937f0ad3b54"
$AcceptedSeed="underreach-29e2-real-equipment-proof"

Write-Host "[29E.5] Focused deterministic equipment/character combat integration tests"
& $Python -m pytest -q `
  tests/test_underreach_29d4_combat_motion_polish.py `
  tests/test_underreach_29e2_real_equipment_assets.py `
  tests/test_underreach_29e3_equipment_material_wear.py `
  tests/test_underreach_29e4_character_material_appearance.py `
  tests/test_underreach_29e5_equipment_character_combat_integration.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}

foreach($Dir in @($E2Out,$E3Out,$Out)){
  if(Test-Path $Dir){Remove-Item -Recurse -Force $Dir}
  New-Item -ItemType Directory -Force -Path $Dir|Out-Null
}

Write-Host "[29E.5] Rebuilding exact accepted 29E.2 real equipment prerequisite"
& $Python $E2Generator --output $E2Proof --source-dir $E2SourceDir --source-manifest $E2SourceManifest --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$E2=Get-Content -Raw $E2Proof|ConvertFrom-Json
if($E2.digest-ne $Accepted29E2Digest){throw "29E.5 source 29E.2 digest changed"}
if([int]$E2.population_count-ne 24 -or [int]$E2.replacement_count-ne 52){throw "29E.5 source 29E.2 accepted counts changed"}
& $UnrealEditorCmd $Project "-ExecutePythonScript=$E2Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $E2Log
$E2Exit=$LASTEXITCODE
if(-not(Test-Path $E2Debug)){Get-Content $E2Log -Tail 160|Write-Host; throw "29E.5 prerequisite 29E.2 Unreal builder produced no diagnostics"}
$E2D=Get-Content -Raw $E2Debug|ConvertFrom-Json
if(-not $E2D.validation.all_pass){throw "29E.5 prerequisite 29E.2 real equipment realization failed"}
Write-Host "[29E.5] 29E.2 real equipment prerequisite PASS: realMeshes=$($E2D.real_static_mesh_asset_count) replacements=$($E2.replacement_count)"
if($E2Exit-ne 0){Write-Warning "29E.2 prerequisite Unreal returned $E2Exit after fresh valid diagnostics; continuing."}

Write-Host "[29E.5] Rebuilding exact accepted 29E.3 equipment material source"
& $Python $E3Generator --output $E3Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$E3=Get-Content -Raw $E3Proof|ConvertFrom-Json
if($E3.digest-ne $Accepted29E3Digest){throw "29E.5 source 29E.3 digest changed"}
if($E3.source_29e2_digest-ne $Accepted29E2Digest){throw "29E.5 source 29E.3 no longer consumes accepted 29E.2"}
if([int]$E3.population_count-ne 24 -or [int]$E3.material_directive_count-ne 52){throw "29E.5 source 29E.3 accepted counts changed"}

Write-Host "[29E.5] Realizing accepted 29E.3 per-Descender equipment materials for integration"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$E3Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $E3Log
$E3Exit=$LASTEXITCODE
if(-not(Test-Path $E3Debug)){Get-Content $E3Log -Tail 160|Write-Host; throw "29E.5 prerequisite 29E.3 Unreal builder produced no diagnostics"}
$E3D=Get-Content -Raw $E3Debug|ConvertFrom-Json
if(-not $E3D.validation.all_pass){throw "29E.5 prerequisite 29E.3 Unreal material realization failed"}
if([int]$E3D.material_instance_count-ne 52){throw "29E.5 prerequisite did not realize all 52 equipment material instances"}
Write-Host "[29E.5] 29E.3 equipment material prerequisite PASS: instances=$($E3D.material_instance_count)"
if($E3Exit-ne 0){Write-Warning "29E.3 prerequisite Unreal returned $E3Exit after fresh valid diagnostics; continuing."}

Write-Host "[29E.5] Generating deterministic integration proof twice"
& $Python $Generator --output $Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $Python $Generator --output $Repro --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json
$Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.digest-ne $Q.digest){throw "29E.5 reproducibility digest mismatch"}
if($P.source_29e4_digest-ne $Accepted29E4Digest){throw "29E.5 source 29E.4 digest changed"}
if($P.source_29e3_digest-ne $Accepted29E3Digest){throw "29E.5 source 29E.3 digest changed"}
if($P.source_29e2_digest-ne $Accepted29E2Digest){throw "29E.5 source 29E.2 digest changed"}
if($P.authoritative-ne $false -or $P.combat_timing_mutation_allowed-ne $false -or $P.combat_outcome_mutation_allowed-ne $false){throw "29E.5 authority boundary changed"}
if([int]$P.population_count-ne 24 -or [int]$P.equipment_integration_directive_count-ne 52){throw "29E.5 accepted integration counts changed"}
$Entries=@($P.entries)
$Species=@($Entries|Select-Object -ExpandProperty species -Unique|Sort-Object)
if(($Species -join ',')-ne 'dwarf,human'){throw "29E.5 Human/Dwarf coverage missing"}
$Variants=@($Entries|Select-Object -ExpandProperty visual_variant -Unique)
if($Variants.Count-lt 4){throw "29E.5 body variant coverage collapsed"}
$Items=@($Entries|ForEach-Object{@($_.equipment_integrations)})
$Visuals=@($Items|Select-Object -ExpandProperty visual_id -Unique|Sort-Object)
if(($Visuals -join ',') -ne 'underreach.armor.breastplate.v1,underreach.armor.helmet.v1,underreach.weapon.sword.v1'){throw "29E.5 equipment visual coverage incomplete"}
Write-Host "[29E.5] Deterministic integration manifest PASS"
Write-Host "digest=$($P.digest) population=$($P.population_count) equipmentIntegrations=$($P.equipment_integration_directive_count) variants=$($Variants.Count)"
Write-Host "source29E4Digest=$($P.source_29e4_digest) source29E3Digest=$($P.source_29e3_digest) source29E2Digest=$($P.source_29e2_digest)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29E.5] Unreal real-equipment + native-combat-animation integration proof"
Write-Host "[29E.5] NullRHI enabled; AnimPose evaluates exact attack/reaction/death poses without viewport playback"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit=$LASTEXITCODE
if(-not(Test-Path $Debug)){Get-Content $UnrealLog -Tail 180|Write-Host; throw "29E.5 Unreal proof produced no diagnostics"}
$D=Get-Content -Raw $Debug|ConvertFrom-Json
$After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if(-not $D.validation.all_pass){
  Write-Host "[29E.5] Diagnostics: $Debug"
  throw "29E.5 Unreal validation flags failed"
}
if($Before-ne $After){throw "29E.5 Unreal modified proof artifact"}
if([int]$D.all_variant_count-ne 6){throw "29E.5 did not validate all six accepted body-variant combat families"}
if([int]$D.attachment_binding_count-lt 8){throw "29E.5 live equipment attachment sample too small"}
if([int]$D.weapon_animated_follow_pass_count-lt 1){throw "29E.5 weapon did not follow animated hand_r"}
if([int]$D.reaction_armor_follow_pass_count-lt 2 -or [int]$D.death_armor_follow_pass_count-lt 2){throw "29E.5 armor reaction/death persistence proof incomplete"}
if([double]$D.max_weapon_grip_alignment_error_cm-gt 0.05){throw "29E.5 weapon grip alignment exceeded tolerance"}
$ObservedVisuals=@($D.observed_equipment_visuals|Sort-Object)
if(($ObservedVisuals -join ',') -ne 'underreach.armor.breastplate.v1,underreach.armor.helmet.v1,underreach.weapon.sword.v1'){throw "29E.5 Unreal equipment coverage incomplete"}
$ObservedSpecies=@($D.observed_species|Sort-Object)
if(($ObservedSpecies -join ',') -ne 'dwarf,human'){throw "29E.5 Unreal Human/Dwarf coverage incomplete"}
Write-Host "[29E.5] Unreal equipment/character combat integration PASS"
Write-Host "variants=$($D.all_variant_count) sampleDescenders=$($D.sample_descender_count) attachments=$($D.attachment_binding_count) animationFollowChecks=$($D.animation_follow_check_count)"
Write-Host "weaponFollow=$($D.weapon_animated_follow_pass_count) reactionArmor=$($D.reaction_armor_follow_pass_count) deathArmor=$($D.death_armor_follow_pass_count) maxGripErrorCm=$($D.max_weapon_grip_alignment_error_cm)"
if($UnrealExit-ne 0){Write-Warning "Unreal returned $UnrealExit after fresh valid diagnostics; accepting artifact validation rather than shutdown status."}

Write-Host "[29E.5] Full repository regression suite"
& $Python -m pytest -q
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29E.5] PASS"
Write-Host "Proof: $Proof"
Write-Host "Diagnostics: $Debug"
Write-Host "Unreal log: $UnrealLog"
