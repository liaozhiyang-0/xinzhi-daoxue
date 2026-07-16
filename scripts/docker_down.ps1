$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Docker = Get-Command docker -ErrorAction SilentlyContinue
if ($Docker) {
    & $Docker.Source compose down
    exit
}

$BundledDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
if (-not (Test-Path $BundledDocker)) {
    throw "docker.exe was not found."
}
& $BundledDocker compose down
