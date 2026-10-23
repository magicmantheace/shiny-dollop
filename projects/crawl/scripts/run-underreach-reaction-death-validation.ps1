param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot; Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"; if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$AttackProfiler=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\profile_mannequin_attacks.py"
$ReactionProfiler=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\profile_underreach_reaction_death_assets.py"
$Generator=Join-Path $RepoRoot "scripts\generate-underreach-reaction-death-binding-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_reaction_death_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29d3"; New-Item -ItemType Directory -Force -Path $Out|Out-Null
$AttackProfiles=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\attack_profiles_measured.json"
$ReactionProfiles=Join-Path $Out "reaction-death-profiles.json"
$Proof=Join-Path $Out "reaction-death-binding-proof.json"; $Repro=Join-Path $Out "reaction-death-binding-proof-repro.json"; $Debug=Join-Path $Out "reaction-death-binding-unreal-debug.json"
$AttackLog=Join-Path $Out "unreal-attack-profiler.log"; $ReactionLog=Join-Path $Out "unreal-reaction-death-profiler.log"; $UnrealLog=Join-Path $Out "unreal-reaction-death-proof.log"

Write-Host "[29D.3] Focused deterministic reaction/death binding tests"
& $Python -m pytest -q tests/test_underreach_29d1_combat_presentation.py tests/test_underreach_29d2_animation_binding.py tests/test_underreach_29d3_reaction_death_binding.py tests/test_attack_variety.py tests/test_animation_transitions.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
foreach($f in @($AttackProfiles,$ReactionProfiles,$Proof,$Repro,$Debug,$AttackLog,$ReactionLog,$UnrealLog)){if(Test-Path $f){Remove-Item -Force $f}}

Write-Host "[29D.3] Freshly measuring accepted real attack assets"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$AttackProfiler" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $AttackLog
if(-not(Test-Path $AttackProfiles)){Get-Content $AttackLog -Tail 100|Write-Host; throw "29D.3 attack profile generation failed"}
$A=Get-Content -Raw $AttackProfiles|ConvertFrom-Json
if(@($A.profiles).Count-lt 4){throw "29D.3 attack profiles incomplete"}

Write-Host "[29D.3] Discovering and measuring real hit-reaction/death assets"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$ReactionProfiler" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $ReactionLog
if(-not(Test-Path $ReactionProfiles)){Get-Content $ReactionLog -Tail 120|Write-Host; throw "29D.3 reaction/death profiler produced no artifact"}
$R=Get-Content -Raw $ReactionProfiles|ConvertFrom-Json
$Reactions=@($R.profiles|Where-Object{$_.kind-eq 'hit_reaction'}); $Deaths=@($R.profiles|Where-Object{$_.kind-eq 'death'})
Write-Host "[29D.3] compatible real assets: reactions=$($Reactions.Count) deaths=$($Deaths.Count) candidates=$($R.candidate_count)"
if($Reactions.Count-lt 1 -or $Deaths.Count-lt 1){
  Write-Host "[29D.3] Compatible candidates discovered:"; @($R.profiles)|ForEach-Object{Write-Host "  $($_.kind): $($_.asset_name)"}
  Write-Host "[29D.3] Rejected candidates:"; @($R.rejected_candidates)|Select-Object -First 30|ForEach-Object{Write-Host "  $($_.asset_name): $($_.reason)"}
  throw "29D.3 requires at least one real Manny-compatible hit reaction and death asset"
}

Write-Host "[29D.3] Generating binding proof twice for reproducibility"
& $Python $Generator --attack-profiles $AttackProfiles --reaction-profiles $ReactionProfiles --output $Proof --seed "underreach-29d3-reaction-death-proof"; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $Python $Generator --attack-profiles $AttackProfiles --reaction-profiles $ReactionProfiles --output $Repro --seed "underreach-29d3-reaction-death-proof"; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json; $Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.reaction_death_binding.digest-ne $Q.reaction_death_binding.digest){throw "29D.3 reproducibility digest mismatch"}
$RB=@($P.reaction_death_binding.bindings|Where-Object{$_.presentation_kind-eq 'hit_reaction'}); $DB=@($P.reaction_death_binding.bindings|Where-Object{$_.presentation_kind-eq 'death'})
if(@($RB|Where-Object{$_.binding_status-ne 'measured_real_asset'}).Count-ne 0 -or @($DB|Where-Object{$_.binding_status-ne 'measured_real_asset'}).Count-ne 0){throw "29D.3 semantic fallback remains in reaction/death path"}
Write-Host "[29D.3] Deterministic real reaction/death binding PASS"
Write-Host "bindingDigest=$($P.reaction_death_binding.digest) reactions=$($RB.Count) deaths=$($DB.Count)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29D.3] Unreal real reaction/death consumer proof"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
if(-not(Test-Path $Debug)){Get-Content $UnrealLog -Tail 120|Write-Host; throw "29D.3 Unreal proof produced no diagnostics"}
$D=Get-Content -Raw $Debug|ConvertFrom-Json; $After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if(-not $D.validation.all_pass){throw "29D.3 Unreal validation flags failed"}; if($Before-ne $After){throw "29D.3 Unreal modified proof"}
Write-Host "[29D.3] Unreal reaction/death proof PASS"
Write-Host "reactions=$($D.reaction_count) deaths=$($D.death_count) reactionAssets=$($D.unique_reaction_assets) deathAssets=$($D.unique_death_assets) maxSync=$($D.max_contact_sync_error_seconds)s"

Write-Host "[29D.3] Full repository regression suite"
& $Python -m pytest -q; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29D.3] PASS"
Write-Host "Profiles: $ReactionProfiles"; Write-Host "Proof: $Proof"; Write-Host "Diagnostics: $Debug"; Write-Host "Profiler log: $ReactionLog"; Write-Host "Unreal log: $UnrealLog"
