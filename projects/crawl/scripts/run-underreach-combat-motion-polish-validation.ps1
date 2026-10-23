param([string]$UnrealEditorCmd="D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
$ErrorActionPreference="Stop"
$RepoRoot=Split-Path -Parent $PSScriptRoot; Set-Location $RepoRoot
$Python=Join-Path $RepoRoot ".venv\Scripts\python.exe"; if(-not(Test-Path $Python)){$Python="python"}
$Project=Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$AttackProfiler=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\profile_mannequin_attacks.py"
$ReactionProfiler=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\profile_underreach_reaction_death_assets.py"
$Generator=Join-Path $RepoRoot "scripts\generate-underreach-combat-motion-polish-proof.py"
$Builder=Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\build_underreach_combat_motion_polish_proof.py"
$Out=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29d4"; New-Item -ItemType Directory -Force -Path $Out|Out-Null
$AttackProfiles=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\attack_profiles_measured.json"
$ReactionDir=Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\underreach-29d3"; New-Item -ItemType Directory -Force -Path $ReactionDir|Out-Null
$ReactionProfiles=Join-Path $ReactionDir "reaction-death-profiles.json"
$Proof=Join-Path $Out "combat-motion-polish-proof.json"; $Repro=Join-Path $Out "combat-motion-polish-proof-repro.json"; $Debug=Join-Path $Out "combat-motion-polish-unreal-debug.json"
$AttackLog=Join-Path $Out "unreal-attack-profiler.log"; $ReactionLog=Join-Path $Out "unreal-reaction-death-profiler.log"; $UnrealLog=Join-Path $Out "unreal-combat-motion-polish-proof.log"

Write-Host "[29D.4] Focused deterministic combat motion polish tests"
& $Python -m pytest -q tests/test_underreach_29d1_combat_presentation.py tests/test_underreach_29d2_animation_binding.py tests/test_underreach_29d3_reaction_death_binding.py tests/test_underreach_29d4_combat_motion_polish.py tests/test_attack_variety.py tests/test_animation_transitions.py
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
foreach($f in @($AttackProfiles,$ReactionProfiles,$Proof,$Repro,$Debug,$AttackLog,$ReactionLog,$UnrealLog)){if(Test-Path $f){Remove-Item -Force $f}}

Write-Host "[29D.4] Freshly measuring accepted attack assets"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$AttackProfiler" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $AttackLog
if(-not(Test-Path $AttackProfiles)){Get-Content $AttackLog -Tail 100|Write-Host; throw "29D.4 attack profiler produced no artifact"}
$A=Get-Content -Raw $AttackProfiles|ConvertFrom-Json
if(@($A.profiles).Count-lt 4){throw "29D.4 attack profiles incomplete"}

Write-Host "[29D.4] Freshly measuring accepted hit-reaction/death assets"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$ReactionProfiler" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $ReactionLog
if(-not(Test-Path $ReactionProfiles)){Get-Content $ReactionLog -Tail 120|Write-Host; throw "29D.4 reaction/death profiler produced no artifact"}
$R=Get-Content -Raw $ReactionProfiles|ConvertFrom-Json
$Reactions=@($R.profiles|Where-Object{$_.kind-eq 'hit_reaction'}); $Deaths=@($R.profiles|Where-Object{$_.kind-eq 'death'})
if($Reactions.Count-lt 1 -or $Deaths.Count-lt 1){throw "29D.4 requires the accepted real reaction/death assets"}
Write-Host "[29D.4] Real profile refresh PASS: attacks=$(@($A.profiles).Count) reactions=$($Reactions.Count) deaths=$($Deaths.Count)"

Write-Host "[29D.4] Generating motion polish proof twice for reproducibility"
& $Python $Generator --attack-profiles $AttackProfiles --reaction-profiles $ReactionProfiles --output $Proof --seed "underreach-29d4-combat-motion-polish-proof"; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
& $Python $Generator --attack-profiles $AttackProfiles --reaction-profiles $ReactionProfiles --output $Repro --seed "underreach-29d4-combat-motion-polish-proof"; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$P=Get-Content -Raw $Proof|ConvertFrom-Json; $Q=Get-Content -Raw $Repro|ConvertFrom-Json
if($P.motion_polish.digest-ne $Q.motion_polish.digest){throw "29D.4 reproducibility digest mismatch"}
$Directives=@($P.motion_polish.directives); $Attacks=@($Directives|Where-Object{$_.presentation_kind-eq 'attack'}); $React=@($Directives|Where-Object{$_.presentation_kind-eq 'hit_reaction'}); $Death=@($Directives|Where-Object{$_.presentation_kind-eq 'death'})
if($Attacks.Count-lt 1 -or $React.Count-lt 1 -or $Death.Count-lt 1){throw "29D.4 proof missing required combat directive type"}
if(@($Attacks|Where-Object{[double]$_.contact_alignment_cm-gt [double]$P.motion_polish.max_pair_alignment_cm}).Count-ne 0){throw "29D.4 pair alignment exceeded bound"}
if(@($React|Where-Object{[double]$_.reaction_displacement_cm-gt [double]$P.motion_polish.max_knockback_cm}).Count-ne 0){throw "29D.4 reaction displacement exceeded bound"}
if(@($Death|Where-Object{$_.corpse_root_lock-ne $true}).Count-ne 0){throw "29D.4 corpse root lock missing"}
Write-Host "[29D.4] Deterministic combat motion polish schedule PASS"
Write-Host "polishDigest=$($P.motion_polish.digest) directives=$($Directives.Count) attacks=$($Attacks.Count) reactions=$($React.Count) deaths=$($Death.Count)"

$Before=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
Write-Host "[29D.4] Unreal combat motion polish consumer proof"
Write-Host "[29D.4] NullRHI enabled so validation does not require a desktop/D3D viewport"
& $UnrealEditorCmd $Project "-ExecutePythonScript=$Builder" -unattended -nop4 -nosplash -NullRHI -NoSound -stdout -FullStdOutLogOutput *> $UnrealLog
if(-not(Test-Path $Debug)){Get-Content $UnrealLog -Tail 120|Write-Host; throw "29D.4 Unreal proof produced no diagnostics"}
$D=Get-Content -Raw $Debug|ConvertFrom-Json; $After=(Get-FileHash -Algorithm SHA256 $Proof).Hash.ToLowerInvariant()
if(-not $D.validation.all_pass){throw "29D.4 Unreal validation flags failed"}
if($Before-ne $After){throw "29D.4 Unreal modified proof artifact"}
Write-Host "[29D.4] Unreal combat motion polish proof PASS"
Write-Host "attacks=$($D.attack_count) reactions=$($D.reaction_count) deaths=$($D.death_count) assets=$($D.unique_asset_count)"
Write-Host "maxAlignmentCm=$($D.max_pair_alignment_cm) maxSlideCm=$($D.max_foot_slide_budget_cm) maxReactionCm=$($D.max_reaction_displacement_cm) maxSync=$($D.max_contact_sync_error_seconds)s"

Write-Host "[29D.4] Full repository regression suite"
& $Python -m pytest -q; if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
Write-Host "[29D.4] PASS"
Write-Host "Proof: $Proof"; Write-Host "Diagnostics: $Debug"; Write-Host "Attack profiler log: $AttackLog"; Write-Host "Reaction/death profiler log: $ReactionLog"; Write-Host "Unreal log: $UnrealLog"
