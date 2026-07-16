$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$DockerCommand = $null
$Docker = Get-Command docker -ErrorAction SilentlyContinue
if ($Docker) {
    $DockerCommand = $Docker.Source
}
if (-not $DockerCommand) {
    $BundledDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $BundledDocker) {
        $DockerCommand = $BundledDocker
    }
}
if (-not $DockerCommand) {
    Write-Warning "Docker not found; no containers were stopped."
    exit 0
}
& $DockerCommand compose down
