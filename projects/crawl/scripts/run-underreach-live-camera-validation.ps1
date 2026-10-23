param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    [int]$SimulationSteps = 90,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run-underreach-live-bridge-validation.ps1"
& $Runner -UnrealEditorCmd $UnrealEditorCmd -SimulationSteps $SimulationSteps -SkipRender:$SkipRender
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
