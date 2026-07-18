[CmdletBinding()]
param([int]$Port = 8000, [switch]$WithCloudPreflight)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Arguments = @("start", "-Port", $Port)
if ($WithCloudPreflight) { $Arguments += "-WithCloud" }
& (Join-Path $RepoRoot "xzd.ps1") @Arguments
exit $LASTEXITCODE
