[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$OpenBrowser,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $Root ".codex-tmp"
$StopFile = Join-Path $RuntimeDir "xzd-supervisor.stop"
$LockFile = Join-Path $RuntimeDir "xzd-supervisor.lock"
$SupervisorLog = Join-Path $RuntimeDir "xzd-supervisor.log"
$Launcher = Join-Path $Root "scripts\team_launcher.py"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

function Get-XzdPython {
    if (Test-Path -LiteralPath $VenvPython) {
        & $VenvPython -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) { return $VenvPython }
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($version in @("3.13", "3.12", "3.11")) {
            & $py.Source "-$version" -c "import sys" *> $null
            if ($LASTEXITCODE -eq 0) {
                return "$($py.Source) -$version"
            }
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    throw "Python 3.11-3.13 was not found."
}

function Write-SupervisorLog([string]$Message) {
    Add-Content -LiteralPath $SupervisorLog -Value "$(Get-Date -Format s) $Message"
}

if ($Stop) {
    Set-Content -LiteralPath $StopFile -Value (Get-Date -Format o)
    Write-SupervisorLog "stop requested"
    try {
        $python = Get-XzdPython
        if ($python -match "^(.+) -3\.(11|12|13)$") {
            & $Matches[1] $Matches[0].Substring($Matches[1].Length + 1) $Launcher stop --port $Port
        } else {
            & $python $Launcher stop --port $Port
        }
        $exitCode = $LASTEXITCODE
    } catch {
        Write-SupervisorLog "stop failed: $($_.Exception.Message)"
        $exitCode = 1
    }
    exit $exitCode
}

Remove-Item -LiteralPath $StopFile -Force -ErrorAction SilentlyContinue

try {
    $lock = [System.IO.File]::Open($LockFile, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch {
    Write-SupervisorLog "another supervisor is already running"
    exit 0
}

try {
    $python = Get-XzdPython
    $browserPending = [bool]$OpenBrowser
    Write-SupervisorLog "supervisor started on port $Port"

    while (-not (Test-Path -LiteralPath $StopFile)) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $stdoutLog = Join-Path $RuntimeDir "xzd-$stamp.stdout.log"
        $stderrLog = Join-Path $RuntimeDir "xzd-$stamp.stderr.log"
        $arguments = @($Launcher, "start", "--port", "$Port")
        if ($browserPending) { $arguments += "--open-browser" }

        Write-SupervisorLog "starting launcher"
        if ($python -match "^(.+) -3\.(11|12|13)$") {
            $child = Start-Process -FilePath $Matches[1] -ArgumentList @($Matches[0].Substring($Matches[1].Length + 1)) + $arguments -WorkingDirectory $Root -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -Wait -PassThru -WindowStyle Hidden
        } else {
            $child = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $Root -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -Wait -PassThru -WindowStyle Hidden
        }
        $browserPending = $false
        Write-SupervisorLog "launcher exited with code $($child.ExitCode); stdout=$stdoutLog stderr=$stderrLog"

        if (Test-Path -LiteralPath $StopFile) { break }
        Start-Sleep -Seconds 5
    }

    Write-SupervisorLog "supervisor stopped"
} finally {
    $lock.Dispose()
}
