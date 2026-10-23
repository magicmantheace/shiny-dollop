param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot; Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"; if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Generator=Join-Path $RepoRoot "scripts\generate-underreach-visual-quality-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_visual_quality_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29e1"; New-Item -ItemType Directory -Force -Path $Out|Out-Null
$Proof=Join-Path $Out "visual-quality-proof.json"; $Repro=Join-Path $Out "visual-quality-proof-repro.json"; $Debug=Join-Path $Out "visual-quality-unreal-debug.json"; $UnrealLog=Join-Path $Out "unreal-visual-quality-proof.log"

Write-Host "[29E.1] Focused character/equipment visual-quality tests"
& $Python -m pytest -q tests/test_character_dna.py tests/test_underreach_29a1_1.py tests/test_underreach_29a2_population.py tests/test_underreach_29d4_combat_motion_polish.py tests/test_underreach_29e1_visual_quality.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
foreach($f in @($Proof,$Repro,$Debug,$UnrealLog)){if(Test-Path $f){Remove-Item -Force $f}}

Write-Host "[29E.1] Generating visual-quality proof twice for reproducibility"
& $Python $Generator --output $Proof --seed "underreach-29e1-visual-quality-proof" --count 24; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $Python $Generator --output $Repro --seed "underreach-29e1-visual-quality-proof" --count 24; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json; $Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.digest-ne $Q.digest){throw "29E.1 deterministic digest mismatch"}
if($P.protocol-ne "underreach.character-equipment-visual-quality.v1" -or $P.authoritative-ne $false){throw "29E.1 protocol/authority invalid"}
$Equipment=@($P.entries|ForEach-Object{$_.equipment})
$ProxyMisrepresentation=@($Equipment|Where-Object{$_.quality_tier-ne 'procedural_proxy' -or $_.asset_realization-ne 'procedural_attachment_geometry' -or $null-ne $_.unreal_asset_path -or $_.production_art_required-ne $true}).Count
if($ProxyMisrepresentation-ne 0){throw "29E.1 proxy realization was misrepresented as loadable/production art"}
Write-Host "[29E.1] Deterministic visual-quality manifest PASS"
Write-Host "digest=$($P.digest) population=$($P.population_count) equipment=$($Equipment.Count)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29E.1] Unreal equipment/material consumer proof"
Write-Host "[29E.1] NullRHI enabled so validation does not require a desktop/D3D viewport"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
$UnrealExit=$LASTEXITCODE
if(-not(Test-Path $Debug)){Get-Content $UnrealLog -Tail 120|Write-Host; throw "29E.1 Unreal proof produced no diagnostics"}
$D=Get-Content -Raw $Debug|ConvertFrom-Json; $After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if($D.protocol-ne "underreach.character-equipment-visual-quality-unreal-debug.v2"){throw "29E.1 unexpected Unreal debug protocol: $($D.protocol)"}
if(-not $D.validation.all_pass){throw "29E.1 Unreal validation flags failed"}
if($Before-ne $After){throw "29E.1 Unreal modified proof artifact"}
if([int]$D.procedural_proxy_directive_count-ne [int]$D.equipment_directive_count){throw "29E.1 not every equipment directive used truthful procedural proxy realization"}
if([int]$D.loadable_equipment_asset_count-ne 0){throw "29E.1 unexpectedly claimed loadable 29A equipment meshes"}
Write-Host "[29E.1] Unreal visual-quality proof PASS"
Write-Host "population=$($D.population_count) equipment=$($D.equipment_directive_count) proceduralProxies=$($D.procedural_proxy_directive_count) plannedProductionAssets=$($D.planned_production_asset_count) materialVariants=$($D.material_variant_count)"
Write-Host "fitScale=$($D.min_fit_scale)..$($D.max_fit_scale) attachmentBones=$($D.attachment_bones -join ',')"
if($UnrealExit-ne 0){Write-Warning "Unreal returned $UnrealExit after fresh valid diagnostics; accepting artifact validation rather than shutdown status."}

Write-Host "[29E.1] Full repository regression suite"
& $Python -m pytest -q; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29E.1] PASS"
Write-Host "Proof: $Proof"; Write-Host "Diagnostics: $Debug"; Write-Host "Unreal log: $UnrealLog"
