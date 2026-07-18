[CmdletBinding()]
param([int]$Port = 8000, [switch]$RefreshDeps)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Arguments = @("start", "-Port", $Port, "-Reload")
if ($RefreshDeps) { $Arguments += "-RefreshDeps" }
& (Join-Path $RepoRoot "xzd.ps1") @Arguments
exit $LASTEXITCODE
