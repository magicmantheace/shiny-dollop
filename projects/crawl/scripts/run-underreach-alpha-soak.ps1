param(
    [double]$Hours = 2.0,
    [switch]$FaultInjection,
    [switch]$Resume,
    [int]$ViewerPort = 8011,
    [string]$StateDirectory = "",
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ($Hours -lt 2.0) { throw "The acceptance soak must run for at least 2 hours." }
if ([string]::IsNullOrWhiteSpace($StateDirectory)) {
    $StateDirectory = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\runtime-soak"
}
$Seconds = [math]::Round($Hours * 3600.0, 3)
& (Join-Path $PSScriptRoot "start-underreach-alpha.ps1") -Profile alpha -DurationSeconds $Seconds -ViewerPort $ViewerPort -StateDirectory $StateDirectory -UnrealEditorCmd $UnrealEditorCmd -FaultInjection:$FaultInjection -Resume:$Resume
if ($LASTEXITCODE -ne 0) { throw "Underreach Alpha soak failed." }
