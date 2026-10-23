param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"
if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$AcceptedSeed="underreach-29e2-real-equipment-proof"

$Accepted29E2Digest="f5fc053be8f23b788321096e6141b88caaaa3f653868e3b0ecd244a62dc8d2f6"
$Accepted29E3Digest="a8ab58180e51a6ae6245daaff75d7cf625c5cfa1e44dd07e49cde00cb9bcaa79"
$Accepted29E4Digest="3614cedb01758a635e945bd506267d659aea120aad52fcf470f48937f0ad3b54"
$Accepted29E5Digest="88d194996aecc56076c136eb493e5d2ce4ca602f77b34e95c2f351bcfc44b4bb"

$E2Generator=Join-Path $RepoRoot "scripts\generate-underreach-real-equipment-proof.py"
$E2Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_real_equipment_proof.py"
$E2Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e2"
$E2Proof=Join-Path $E2Out "real-equipment-proof.json"
$E2SourceManifest=Join-Path $E2Out "source-manifest.json"
$E2SourceDir=Join-Path $E2Out "source"
$E2Debug=Join-Path $E2Out "real-equipment-unreal-debug.json"
$E2Log=Join-Path $E2Out "unreal-29e6-prerequisite-real-equipment.log"

$E3Generator=Join-Path $RepoRoot "scripts\generate-underreach-equipment-material-wear-proof.py"
$E3Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_equipment_material_wear_proof.py"
$E3Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e3"
$E3Proof=Join-Path $E3Out "equipment-material-wear-proof.json"
$E3Debug=Join-Path $E3Out "equipment-material-unreal-debug.json"
$E3Log=Join-Path $E3Out "unreal-29e6-prerequisite-equipment-material.log"

$E4Generator=Join-Path $RepoRoot "scripts\generate-underreach-character-material-appearance-proof.py"
$E4Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_character_material_appearance_proof.py"
$E4Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e4"
$E4Proof=Join-Path $E4Out "character-material-appearance-proof.json"
$E4Debug=Join-Path $E4Out "character-material-unreal-debug.json"
$E4Log=Join-Path $E4Out "unreal-29e6-prerequisite-character-material.log"

$E5Generator=Join-Path $RepoRoot "scripts\generate-underreach-equipment-character-combat-integration-proof.py"
$E5Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e5"
$E5Proof=Join-Path $E5Out "equipment-character-combat-integration-proof.json"

$Generator=Join-Path $RepoRoot "scripts\generate-underreach-character-visual-polish-render-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_character_visual_polish_render_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e6"
$Proof=Join-Path $Out "character-visual-polish-render-proof.json"
$Repro=Join-Path $Out "character-visual-polish-render-proof-repro.json"
$Debug=Join-Path $Out "character-visual-polish-render-unreal-debug.json"
$RenderDir=Join-Path $Out "renders"
$UnrealLog=Join-Path $Out "unreal-character-visual-polish-render.log"

Write-Host "[29E.6] Focused deterministic character visual polish/render tests"
& $Python -m pytest -q `
  tests/test_underreach_29e2_real_equipment_assets.py `
  tests/test_underreach_29e3_equipment_material_wear.py `
  tests/test_underreach_29e4_character_material_appearance.py `
  tests/test_underreach_29e5_equipment_character_combat_integration.py `
  tests/test_underreach_29e6_character_visual_polish_render.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}

foreach($Dir in @($E2Out,$E3Out,$E4Out,$E5Out,$Out)){
  if(Test-Path $Dir){Remove-Item -Recurse -Force $Dir}
  New-Item -ItemType Directory -Force -Path $Dir|Out-Null
}

Write-Host "[29E.6] Rebuilding exact accepted 29E.2 real equipment prerequisite"
& $Python $E2Generator --output $E2Proof --source-dir $E2SourceDir --source-manifest $E2SourceManifest --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$E2=Get-Content -Raw $E2Proof|ConvertFrom-Json
if($E2.digest-ne $Accepted29E2Digest){throw "29E.6 source 29E.2 digest changed"}
if([int]$E2.population_count-ne 24 -or [int]$E2.replacement_count-ne 52){throw "29E.6 source 29E.2 counts changed"}
& $UnrealEditorCmd $Project "-ExecutePythonScript=$E2Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $E2Log
$E2Exit=$LASTEXITCODE
if(-not(Test-Path $E2Debug)){Get-Content $E2Log -Tail 180|Write-Host; throw "29E.6 prerequisite 29E.2 produced no diagnostics"}
$E2D=Get-Content -Raw $E2Debug|ConvertFrom-Json
if(-not $E2D.validation.all_pass){throw "29E.6 prerequisite 29E.2 realization failed"}
Write-Host "[29E.6] 29E.2 prerequisite PASS: realMeshes=$($E2D.real_static_mesh_asset_count) replacements=$($E2.replacement_count)"
if($E2Exit-ne 0){Write-Warning "29E.2 prerequisite Unreal returned $E2Exit after valid diagnostics; continuing."}

Write-Host "[29E.6] Rebuilding exact accepted 29E.3 equipment material prerequisite"
& $Python $E3Generator --output $E3Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$E3=Get-Content -Raw $E3Proof|ConvertFrom-Json
if($E3.digest-ne $Accepted29E3Digest -or $E3.source_29e2_digest-ne $Accepted29E2Digest){throw "29E.6 source 29E.3 provenance changed"}
if([int]$E3.population_count-ne 24 -or [int]$E3.material_directive_count-ne 52){throw "29E.6 source 29E.3 counts changed"}
& $UnrealEditorCmd $Project "-ExecutePythonScript=$E3Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $E3Log
$E3Exit=$LASTEXITCODE
if(-not(Test-Path $E3Debug)){Get-Content $E3Log -Tail 180|Write-Host; throw "29E.6 prerequisite 29E.3 produced no diagnostics"}
$E3D=Get-Content -Raw $E3Debug|ConvertFrom-Json
if(-not $E3D.validation.all_pass -or [int]$E3D.material_instance_count-ne 52){throw "29E.6 prerequisite 29E.3 material realization failed"}
Write-Host "[29E.6] 29E.3 prerequisite PASS: equipmentMaterialInstances=$($E3D.material_instance_count)"
if($E3Exit-ne 0){Write-Warning "29E.3 prerequisite Unreal returned $E3Exit after valid diagnostics; continuing."}

Write-Host "[29E.6] Rebuilding exact accepted 29E.4 character material prerequisite"
& $Python $E4Generator --output $E4Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$E4=Get-Content -Raw $E4Proof|ConvertFrom-Json
if($E4.digest-ne $Accepted29E4Digest -or $E4.source_29e3_digest-ne $Accepted29E3Digest){throw "29E.6 source 29E.4 provenance changed"}
if([int]$E4.population_count-ne 24 -or [int]$E4.material_directive_count-ne 96){throw "29E.6 source 29E.4 counts changed"}
& $UnrealEditorCmd $Project "-ExecutePythonScript=$E4Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $E4Log
$E4Exit=$LASTEXITCODE
if(-not(Test-Path $E4Debug)){Get-Content $E4Log -Tail 200|Write-Host; throw "29E.6 prerequisite 29E.4 produced no diagnostics"}
$E4D=Get-Content -Raw $E4Debug|ConvertFrom-Json
if(-not $E4D.validation.all_pass -or [int]$E4D.material_instance_count-ne 96){throw "29E.6 prerequisite 29E.4 character material realization failed"}
Write-Host "[29E.6] 29E.4 prerequisite PASS: characterMaterialInstances=$($E4D.material_instance_count) categories=$($E4D.observed_slot_categories -join ',')"
if($E4Exit-ne 0){Write-Warning "29E.4 prerequisite Unreal returned $E4Exit after valid diagnostics; continuing."}

Write-Host "[29E.6] Rebuilding exact accepted 29E.5 integration source"
& $Python $E5Generator --output $E5Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$E5=Get-Content -Raw $E5Proof|ConvertFrom-Json
if($E5.digest-ne $Accepted29E5Digest){throw "29E.6 source 29E.5 digest changed"}
if($E5.source_29e4_digest-ne $Accepted29E4Digest -or $E5.source_29e3_digest-ne $Accepted29E3Digest -or $E5.source_29e2_digest-ne $Accepted29E2Digest){throw "29E.6 source 29E.5 provenance changed"}
if([int]$E5.population_count-ne 24 -or [int]$E5.equipment_integration_directive_count-ne 52){throw "29E.6 source 29E.5 counts changed"}
Write-Host "[29E.6] 29E.5 prerequisite PASS: digest=$($E5.digest) equipmentIntegrations=$($E5.equipment_integration_directive_count)"

Write-Host "[29E.6] Generating deterministic render proof twice"
& $Python $Generator --output $Proof --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $Python $Generator --output $Repro --seed $AcceptedSeed --count 24
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json
$Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.digest-ne $Q.digest){throw "29E.6 reproducibility digest mismatch"}
if($P.source_29e5_digest-ne $Accepted29E5Digest -or $P.source_29e4_digest-ne $Accepted29E4Digest){throw "29E.6 accepted source chain changed"}
if($P.authoritative-ne $false -or $P.material_identity_mutation_allowed-ne $false){throw "29E.6 authority boundary changed"}
if([int]$P.population_count-ne 24 -or @($P.shots).Count-ne 4){throw "29E.6 render plan counts changed"}
$Bands=@($P.shots|Select-Object -ExpandProperty distance_band)
if(($Bands -join ',')-ne 'near,near,mid,far'){throw "29E.6 near/mid/far shot contract changed"}
$Distances=@($P.shots|ForEach-Object{[double]$_.camera_distance_cm})
if(($Distances -join ',')-ne '750,750,1300,2400'){throw "29E.6 camera distances changed"}
$Crowd=@($P.shots[3].descender_ids)
if($Crowd.Count-lt 10){throw "29E.6 crowd sample too small"}
Write-Host "[29E.6] Deterministic render manifest PASS"
Write-Host "digest=$($P.digest) population=$($P.population_count) shots=$(@($P.shots).Count) crowd=$($Crowd.Count)"
Write-Host "source29E5Digest=$($P.source_29e5_digest) source29E4Digest=$($P.source_29e4_digest) source29E3Digest=$($P.source_29e3_digest)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29E.6] Unreal GPU offscreen full-body/material/camera-distance/crowd render proof"
Write-Host "[29E.6] Real RHI enabled with -RenderOffScreen; four 1280x720 PNG proof frames will be exported"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -RenderOffScreen -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit=$LASTEXITCODE
if(-not(Test-Path $Debug)){
  Get-Content $UnrealLog -Tail 220|Write-Host
  throw "29E.6 Unreal render proof produced no diagnostics"
}
$D=Get-Content -Raw $Debug|ConvertFrom-Json
$After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if(-not $D.validation.all_pass){
  Write-Host "[29E.6] Diagnostics: $Debug"
  throw "29E.6 Unreal render validation flags failed"
}
if($Before-ne $After){throw "29E.6 Unreal modified proof artifact"}
if([int]$D.render_count-ne 4){throw "29E.6 did not produce all four render proofs"}
$ShotResults=@($D.shot_results)
if(@($ShotResults|Where-Object{-not $_.render_valid}).Count-ne 0){throw "29E.6 one or more rendered shots failed validation"}
if(@($ShotResults|Where-Object{[int64]$_.file_bytes-lt 4096}).Count-ne 0){throw "29E.6 one or more PNG render files are unexpectedly small"}
if(@($ShotResults|Where-Object{-not $_.pixel_metrics.nonblank}).Count-ne 0){throw "29E.6 one or more render targets were blank"}
if(@($ShotResults|Where-Object{-not $_.framing.fits_safe_frame}).Count-ne 0){throw "29E.6 one or more camera-distance shots clipped the safe frame"}
$ObservedVisuals=@($D.observed_equipment_visuals|Sort-Object)
if(($ObservedVisuals -join ',')-ne 'underreach.armor.breastplate.v1,underreach.armor.helmet.v1,underreach.weapon.sword.v1'){throw "29E.6 render proof did not include all equipment visuals"}
Write-Host "[29E.6] Unreal character visual polish/render proof PASS"
foreach($Shot in $ShotResults){
  Write-Host "shot=$($Shot.shot_id) band=$($Shot.distance_band) bytes=$($Shot.file_bytes) nonBlack=$($Shot.pixel_metrics.non_black_sample_count) colorBins=$($Shot.pixel_metrics.unique_quantized_color_bins) safeX=$([math]::Round([double]$Shot.framing.max_abs_projected_x,3)) safeY=$([math]::Round([double]$Shot.framing.max_abs_projected_y,3))"
}
if($UnrealExit-ne 0){Write-Warning "Unreal returned $UnrealExit after fresh valid render diagnostics; accepting artifact validation rather than shutdown status."}

Write-Host "[29E.6] Full repository regression suite"
& $Python -m pytest -q
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29E.6] PASS"
Write-Host "Proof: $Proof"
Write-Host "Diagnostics: $Debug"
Write-Host "Renders: $RenderDir"
Write-Host "Unreal log: $UnrealLog"
