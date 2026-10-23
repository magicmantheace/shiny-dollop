param(
    [switch]$SkipDashboard,
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found at $Python. Create .venv and install .[test] first."
}

$ReportDir = Join-Path $RepoRoot "validation"
$ReportPath = Join-Path $ReportDir "LOCAL_VALIDATION.md"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

function Invoke-CapturedNative {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $originalPythonPath = $env:PYTHONPATH
    try {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        $output = & $FilePath @Arguments 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
    }
    finally {
        if ($null -eq $originalPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        }
        else {
            $env:PYTHONPATH = $originalPythonPath
        }
    }

    [pscustomobject]@{
        Output = $output.TrimEnd()
        ExitCode = $exitCode
    }
}

function Add-CodeBlock {
    param(
        [Parameter(Mandatory = $true)][System.Text.StringBuilder]$Builder,
        [Parameter(Mandatory = $true)][string]$Text
    )

    [void]$Builder.AppendLine('```text')
    [void]$Builder.AppendLine($Text)
    [void]$Builder.AppendLine('```')
    [void]$Builder.AppendLine()
}

$started = Get-Date
$branch = (git branch --show-current).Trim()
$commit = (git rev-parse HEAD).Trim()
$statusBefore = (git status --short | Out-String).TrimEnd()
$pythonVersion = (& $Python --version 2>&1 | Out-String).Trim()
$nodeVersion = (& node --version 2>&1 | Out-String).Trim()
$npmVersion = (& npm --version 2>&1 | Out-String).Trim()

Write-Host "LivingWorld local validation"
Write-Host "Branch: $branch"
Write-Host "Commit: $commit"
Write-Host ""

Write-Host "[1/5] Slice 6 continent/frontier/warfare/balance/benchmark/API tests..."
$sliceTests = Invoke-CapturedNative -FilePath $Python -Arguments @(
    "-m", "pytest",
    "tests\test_continent_generation.py",
    "tests\test_migration.py",
    "tests\test_border_policy.py",
    "tests\test_frontier.py",
    "tests\test_warfare.py",
    "tests\test_benchmark.py",
    "tests\test_long_term_balance.py",
    "tests\test_api_continent.py",
    "tests\test_api_border_policy.py",
    "tests\test_api_frontier.py",
    "tests\test_api_warfare.py",
    "-v"
)
Write-Host $sliceTests.Output

Write-Host ""
Write-Host "[2/5] v0.3 politics, balance, collapse, benchmark, and API tests..."
$politicsTests = Invoke-CapturedNative -FilePath $Python -Arguments @(
    "-m", "pytest",
    "tests\test_politics.py",
    "tests\test_politics_balance.py",
    "tests\test_political_collapse.py",
    "tests\test_politics_benchmark.py",
    "tests\test_politics_integrity.py",
    "tests\test_api_politics.py",
    "-v"
)
Write-Host $politicsTests.Output

Write-Host ""
Write-Host "[3/5] Full backend regression..."
$fullTests = Invoke-CapturedNative -FilePath $Python -Arguments @("-m", "pytest", "-v")
Write-Host $fullTests.Output

Write-Host ""
Write-Host "[4/5] Front/supply/siege/peace smoke test..."
$smokeCode = @'
from livingworld.continent_generation import generate_continent_world
from livingworld.warfare import end_war, refresh_fronts, update_army_supply, update_sieges_and_occupations
from livingworld.world_engine import FinalWorldEngine

w = generate_continent_world("local-validation-slice5", "Eldara")
engine = FinalWorldEngine(w)
attacker_id, defender_id = sorted(w.kingdoms)[:2]
war = engine.declare_war(attacker_id, defender_id, "validation frontier war", source="local-validation")
before_population = w.total_population
fronts = refresh_fronts(engine, war)
assert fronts
update_army_supply(engine, war)
attacker_army = w.armies[w.kingdoms[attacker_id].army_ids[0]]
assert 0.05 <= attacker_army.supply_efficiency <= 1.0
print(f"Fronts: {len(fronts)}; attacker supply: {attacker_army.supply_efficiency:.2f}")

target = next(s for s in w.settlements.values() if s.kingdom_id == defender_id and s.id != w.kingdoms[defender_id].capital_settlement_id)
target.infrastructure["defenses"] = 0.05
attacker_army.location_settlement_id = target.id
attacker_army.destination_settlement_id = None
attacker_army.troop_count = 8000
attacker_army.readiness = 1.0
attacker_army.morale = 1.0
attacker_army.supply_efficiency = 1.0
for _ in range(20):
    update_sieges_and_occupations(engine, war)
    if target.occupied_by_kingdom_id == attacker_id:
        break
assert target.occupied_by_kingdom_id == attacker_id
print(f"Occupied: {target.name}; siege complete")

end_war(engine, war, attacker_id, "local validation peace")
assert target.kingdom_id == attacker_id
assert target.id in war.peace_terms["ceded_settlement_ids"]
assert w.total_population == before_population
print(f"Peace ceded {target.name}; population still {w.total_population}")
'@
$smokePath = Join-Path ([System.IO.Path]::GetTempPath()) ("livingworld-smoke-{0}.py" -f [guid]::NewGuid().ToString("N"))
try {
    Set-Content -Path $smokePath -Value $smokeCode -Encoding UTF8
    $smoke = Invoke-CapturedNative -FilePath $Python -Arguments @($smokePath)
}
finally {
    Remove-Item -Path $smokePath -Force -ErrorAction SilentlyContinue
}
Write-Host $smoke.Output

$dashboard = [pscustomobject]@{ Output = "Skipped by -SkipDashboard"; ExitCode = 0 }
if (-not $SkipDashboard) {
    Write-Host ""
    Write-Host "[5/5] Dashboard production build..."
    Push-Location (Join-Path $RepoRoot "dashboard")
    try {
        $dashboard = Invoke-CapturedNative -FilePath "npm.cmd" -Arguments @("run", "build")
    }
    finally {
        Pop-Location
    }
    Write-Host $dashboard.Output
}
else {
    Write-Host ""
    Write-Host "[5/5] Dashboard production build skipped."
}

$finished = Get-Date
$duration = $finished - $started
$allPassed = ($sliceTests.ExitCode -eq 0) -and ($politicsTests.ExitCode -eq 0) -and ($fullTests.ExitCode -eq 0) -and ($smoke.ExitCode -eq 0) -and ($dashboard.ExitCode -eq 0)
$overall = if ($allPassed) { "PASS" } else { "FAIL" }

$builder = [System.Text.StringBuilder]::new()
[void]$builder.AppendLine("# Local Validation Report")
[void]$builder.AppendLine()
[void]$builder.AppendLine("- **Overall:** $overall")
[void]$builder.AppendLine("- **Generated:** $($finished.ToString('yyyy-MM-dd HH:mm:ss K'))")
[void]$builder.AppendLine("- **Branch:** ``$branch``")
[void]$builder.AppendLine("- **Code commit tested:** ``$commit``")
[void]$builder.AppendLine("- **Duration:** $([math]::Round($duration.TotalSeconds, 2)) seconds")
[void]$builder.AppendLine("- **Python:** $pythonVersion")
[void]$builder.AppendLine("- **Node:** $nodeVersion")
[void]$builder.AppendLine("- **npm:** $npmVersion")
[void]$builder.AppendLine()

[void]$builder.AppendLine("## Working tree before validation")
[void]$builder.AppendLine()
if ([string]::IsNullOrWhiteSpace($statusBefore)) {
    Add-CodeBlock -Builder $builder -Text "clean"
}
else {
    Add-CodeBlock -Builder $builder -Text $statusBefore
}

[void]$builder.AppendLine("## Slice 6 continent/frontier/warfare/balance/benchmark/API tests")
[void]$builder.AppendLine()
[void]$builder.AppendLine("Exit code: **$($sliceTests.ExitCode)**")
[void]$builder.AppendLine()
Add-CodeBlock -Builder $builder -Text $sliceTests.Output

[void]$builder.AppendLine("## v0.3 politics, balance, collapse, benchmark, and API tests")
[void]$builder.AppendLine()
[void]$builder.AppendLine("Exit code: **$($politicsTests.ExitCode)**")
[void]$builder.AppendLine()
Add-CodeBlock -Builder $builder -Text $politicsTests.Output

[void]$builder.AppendLine("## Full backend regression")
[void]$builder.AppendLine()
[void]$builder.AppendLine("Exit code: **$($fullTests.ExitCode)**")
[void]$builder.AppendLine()
Add-CodeBlock -Builder $builder -Text $fullTests.Output

[void]$builder.AppendLine("## Front/supply/siege/peace smoke test")
[void]$builder.AppendLine()
[void]$builder.AppendLine("Exit code: **$($smoke.ExitCode)**")
[void]$builder.AppendLine()
Add-CodeBlock -Builder $builder -Text $smoke.Output

[void]$builder.AppendLine("## Dashboard production build")
[void]$builder.AppendLine()
[void]$builder.AppendLine("Exit code: **$($dashboard.ExitCode)**")
[void]$builder.AppendLine()
Add-CodeBlock -Builder $builder -Text $dashboard.Output

Set-Content -Path $ReportPath -Value $builder.ToString() -Encoding UTF8
Write-Host ""
Write-Host "Validation report written to validation\LOCAL_VALIDATION.md"

if (-not $SkipPush) {
    Write-Host "Committing validation report only..."
    git add -- "validation/LOCAL_VALIDATION.md"
    git commit -m "Update local validation report"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not commit validation report."
    }

    Write-Host "Pushing report to origin/$branch..."
    git push origin "HEAD:$branch"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not push validation report."
    }

    Write-Host "Report pushed successfully."
}
else {
    Write-Host "Push skipped by -SkipPush."
}

Write-Host ""
Write-Host "OVERALL: $overall"
if (-not $allPassed) {
    exit 1
}
exit 0
