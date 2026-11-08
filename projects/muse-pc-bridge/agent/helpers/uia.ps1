# muse-pc-bridge UI Automation helper (v1 S2).
#
# Fixed, agent-shipped script. The bridge agent writes a JSON request
# to a temp file and invokes this script with -In <path>; the script
# prints exactly one JSON object to stdout. The client never supplies
# script text — only the JSON parameters below.
#
# Actions:
#   windows    list top-level windows
#   tree       control tree of a window (or the desktop root)
#   find       find a control by name inside a window
#   invoke     invoke a control found by name (InvokePattern)
#   get_value  read a control's ValuePattern value (or its name)
#   set_value  set a control's ValuePattern value
#
# Window targeting: "hwnd" (integer) wins; otherwise "window_title"
# is a substring match against top-level window names; otherwise the
# desktop root is used (tree/windows only).

param([Parameter(Mandatory = $true)][string]$In)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    @{ error = $Message } | ConvertTo-Json -Compress | Write-Output
    exit 1
}

try {
    $request = Get-Content -Raw -Path $In | ConvertFrom-Json
} catch {
    Fail "could not parse request JSON: $($_.Exception.Message)"
}

try {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
} catch {
    Fail "UI Automation assemblies unavailable: $($_.Exception.Message)"
}

$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]

function Get-Bounds($el) {
    $r = $el.Current.BoundingRectangle
    if ($r.IsEmpty) { return $null }
    return @{ x = [int]$r.X; y = [int]$r.Y; width = [int]$r.Width; height = [int]$r.Height }
}

function Describe-El($el) {
    $ct = $el.Current.ControlType.ProgrammaticName -replace '^ControlType\.', ''
    return @{
        name           = $el.Current.Name
        control_type   = $ct
        automation_id  = $el.Current.AutomationId
        class_name     = $el.Current.ClassName
        process_id     = $el.Current.ProcessId
        hwnd           = $el.Current.NativeWindowHandle
        is_enabled     = $el.Current.IsEnabled
        is_offscreen   = $el.Current.IsOffscreen
        bounds         = Get-Bounds $el
    }
}

function Find-Window($req) {
    $root = $AE::RootElement
    if ($req.PSObject.Properties.Name -contains 'hwnd' -and $req.hwnd) {
        try {
            return [System.Windows.Automation.AutomationElement]::FromHandle(
                [IntPtr]::new([int64]$req.hwnd))
        } catch {
            Fail "no window with hwnd $($req.hwnd)"
        }
    }
    if ($req.PSObject.Properties.Name -contains 'window_title' -and $req.window_title) {
        $cond = New-Object System.Windows.Automation.PropertyCondition(
            $AE::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Window)
        $wins = $root.FindAll($TS::Children, $cond)
        foreach ($w in $wins) {
            if ($w.Current.Name -like "*$($req.window_title)*") { return $w }
        }
        Fail "no top-level window matching title '$($req.window_title)'"
    }
    return $root
}

function Find-ByName($scope, $req) {
    $name = [string]$req.name
    $cond = New-Object System.Windows.Automation.PropertyCondition(
        $AE::NameProperty, $name)
    $found = $scope.FindAll($TS::Descendants, $cond)
    $list = @()
    foreach ($el in $found) {
        if ($req.PSObject.Properties.Name -contains 'control_type' -and $req.control_type) {
            $ct = $el.Current.ControlType.ProgrammaticName -replace '^ControlType\.', ''
            if ($ct -ne [string]$req.control_type) { continue }
        }
        $list += $el
    }
    return $list
}

$action = [string]$request.action

try {
    switch ($action) {
        "windows" {
            $cond = New-Object System.Windows.Automation.PropertyCondition(
                $AE::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::Window)
            $wins = $AE::RootElement.FindAll($TS::Children, $cond)
            $out = @()
            foreach ($w in $wins) { $out += Describe-El $w }
            @{ windows = $out; count = $out.Count } | ConvertTo-Json -Depth 5 -Compress | Write-Output
        }
        "tree" {
            $target = Find-Window $request
            $maxDepth = 3
            if ($request.PSObject.Properties.Name -contains 'max_depth') {
                $maxDepth = [Math]::Max(0, [Math]::Min(10, [int]$request.max_depth))
            }
            $script:budget = 200
            if ($request.PSObject.Properties.Name -contains 'max_nodes') {
                $script:budget = [Math]::Max(1, [Math]::Min(2000, [int]$request.max_nodes))
            }
            $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
            function Build-Tree($el, $depth) {
                $node = Describe-El $el
                $script:budget -= 1
                if ($depth -lt $maxDepth -and $script:budget -gt 0) {
                    $children = @()
                    $child = $walker.GetFirstChild($el)
                    while ($null -ne $child -and $script:budget -gt 0) {
                        $children += Build-Tree $child ($depth + 1)
                        $child = $walker.GetNextSibling($child)
                    }
                    if ($children.Count -gt 0) { $node.children = $children }
                }
                return $node
            }
            $tree = Build-Tree $target 0
            @{ tree = $tree } | ConvertTo-Json -Depth 20 -Compress | Write-Output
        }
        "find" {
            $scope = Find-Window $request
            $matches = Find-ByName $scope $request
            if ($matches.Count -eq 0) {
                @{ found = $false; count = 0 } | ConvertTo-Json -Compress | Write-Output
            } else {
                $d = Describe-El $matches[0]
                $d.found = $true
                $d.count = $matches.Count
                $d | ConvertTo-Json -Depth 5 -Compress | Write-Output
            }
        }
        "invoke" {
            $scope = Find-Window $request
            $matches = Find-ByName $scope $request
            if ($matches.Count -eq 0) { Fail "no control named '$($request.name)'" }
            $el = $matches[0]
            try {
                $pattern = $el.GetCurrentPattern(
                    [System.Windows.Automation.InvokePattern]::Pattern)
            } catch {
                Fail "control '$($request.name)' does not support InvokePattern"
            }
            $pattern.Invoke()
            @{ invoked = $true; name = $el.Current.Name } | ConvertTo-Json -Compress | Write-Output
        }
        "get_value" {
            $scope = Find-Window $request
            $matches = Find-ByName $scope $request
            if ($matches.Count -eq 0) { Fail "no control named '$($request.name)'" }
            $el = $matches[0]
            $value = $null
            try {
                $pattern = $el.GetCurrentPattern(
                    [System.Windows.Automation.ValuePattern]::Pattern)
                $value = $pattern.Current.Value
            } catch {
                $value = $el.Current.Name
            }
            @{ value = $value; name = $el.Current.Name } | ConvertTo-Json -Compress | Write-Output
        }
        "set_value" {
            $scope = Find-Window $request
            $matches = Find-ByName $scope $request
            if ($matches.Count -eq 0) { Fail "no control named '$($request.name)'" }
            $el = $matches[0]
            try {
                $pattern = $el.GetCurrentPattern(
                    [System.Windows.Automation.ValuePattern]::Pattern)
            } catch {
                Fail "control '$($request.name)' does not support ValuePattern"
            }
            if ($pattern.Current.IsReadOnly) {
                Fail "control '$($request.name)' is read-only"
            }
            $pattern.SetValue([string]$request.value)
            @{ ok = $true; name = $el.Current.Name } | ConvertTo-Json -Compress | Write-Output
        }
        default {
            Fail "unknown action: $action"
        }
    }
} catch {
    Fail $_.Exception.Message
}
