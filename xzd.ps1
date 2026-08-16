[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "doctor", "repair", "preflight", "index")]
    [string]$Command = "start",
    [int]$Port = 8000,
    [switch]$Reload,
    [switch]$ForceReload,
    [switch]$RefreshDeps,
    [switch]$OpenBrowser,
    [ValidateSet("CT", "AE", "DE", "SS", "DSP", "COMM")]
    [string]$Course,
    [switch]$TextOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

function Find-XzdPython {
    if (Test-Path -LiteralPath $VenvPython) {
        try {
            & $VenvPython -c "import sys" *> $null
            if ($LASTEXITCODE -eq 0) { return $VenvPython }
        } catch {
            # Fall through to a system interpreter so repair can rebuild .venv.
        }
    }
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        foreach ($Version in @("3.13", "3.12", "3.11")) {
            & $PyLauncher.Source "-$Version" -c "import sys; print(sys.executable)" *> $null
            if ($LASTEXITCODE -eq 0) { return $PyLauncher.Source }
        }
    }
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if ($Python) { return $Python.Source }
    throw "Python 3.11-3.13 was not found. Install Python and try again."
}

$Python = Find-XzdPython
$Launcher = Join-Path $RepoRoot "scripts\team_launcher.py"
$Arguments = @($Launcher, $Command)
if ($Command -eq "start") {
    $Arguments += @("--port", "$Port")
    if ($Reload) { $Arguments += "--reload" }
    if ($ForceReload) { $Arguments += "--force-reload" }
    if ($RefreshDeps) { $Arguments += "--refresh-deps" }
    if ($OpenBrowser) { $Arguments += "--open-browser" }
} elseif ($Command -eq "stop" -or $Command -eq "doctor") {
    $Arguments += @("--port", "$Port")
} elseif ($Command -eq "repair") {
    $Arguments += @("--port", "$Port")
} elseif ($Command -eq "preflight") {
} elseif ($Command -eq "index") {
    if ($Course) { $Arguments += @("--course", $Course) }
    if ($TextOnly) { $Arguments += "--text-only" }
}

if ((Split-Path -Leaf $Python) -eq "py.exe" -and -not (Test-Path -LiteralPath $VenvPython)) {
    foreach ($Version in @("3.13", "3.12", "3.11")) {
        & $Python "-$Version" $Launcher $Arguments[1..($Arguments.Length - 1)]
        if ($LASTEXITCODE -ne 103) { exit $LASTEXITCODE }
    }
    exit 1
}

& $Python @Arguments
exit $LASTEXITCODE
