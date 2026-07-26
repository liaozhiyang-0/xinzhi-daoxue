$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
& (Join-Path $RepoRoot "xzd.ps1") stop
exit $LASTEXITCODE
