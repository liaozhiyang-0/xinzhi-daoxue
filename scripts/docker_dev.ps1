$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Resolve-DockerCommand {
    $Command = Get-Command docker -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $BundledDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $BundledDocker) {
        $env:PATH = "$(Split-Path -Parent $BundledDocker);$env:PATH"
        return $BundledDocker
    }

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed and winget is unavailable."
    }

    Write-Host "[xzd] Docker Desktop is missing. Installing with winget..."
    winget install `
        --id Docker.DockerDesktop `
        --exact `
        --silent `
        --accept-package-agreements `
        --accept-source-agreements `
        --disable-interactivity
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop installation failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path $BundledDocker)) {
        throw "Docker Desktop installation completed but docker.exe was not found."
    }
    $env:PATH = "$(Split-Path -Parent $BundledDocker);$env:PATH"
    return $BundledDocker
}

function Test-DockerEngine([string]$DockerCommand) {
    $PreviousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $DockerCommand info *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $PreviousErrorAction
    }
}

function Wait-DockerEngine([string]$DockerCommand) {
    if (Test-DockerEngine $DockerCommand) {
        return
    }

    $DockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $DockerDesktop)) {
        throw "Docker Desktop executable was not found."
    }
    if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
        Write-Host "[xzd] Starting Docker Desktop..."
        Start-Process -FilePath $DockerDesktop -WindowStyle Hidden
    }

    $Deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 2
        if (Test-DockerEngine $DockerCommand) {
            Write-Host "[xzd] Docker Engine is ready."
            return
        }
        Write-Host "[xzd] Waiting for Docker Engine..."
    } while ((Get-Date) -lt $Deadline)

    throw "Docker Engine did not become ready within 3 minutes."
}

function Wait-ComposeHealth([string]$DockerCommand) {
    $Containers = @("xzd-postgres", "xzd-redis", "xzd-minio", "xzd-api")
    $Deadline = (Get-Date).AddMinutes(3)
    do {
        $AllHealthy = $true
        foreach ($Container in $Containers) {
            $PreviousErrorAction = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $Status = & $DockerCommand inspect `
                --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" `
                $Container 2>$null
            $InspectExitCode = $LASTEXITCODE
            $ErrorActionPreference = $PreviousErrorAction
            if ($InspectExitCode -ne 0 -or $Status -ne "healthy") {
                $AllHealthy = $false
            }
        }
        if ($AllHealthy) {
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $Deadline)

    & $DockerCommand compose ps
    & $DockerCommand compose logs --tail 100
    throw "Docker services did not become healthy within 3 minutes."
}

$Docker = Resolve-DockerCommand
Wait-DockerEngine $Docker

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Warning "Created .env from .env.example. Change development passwords."
}

Write-Host "[xzd] Validating Docker Compose..."
& $Docker compose config --quiet

Write-Host "[xzd] Building and starting services..."
& $Docker compose up -d --build
Wait-ComposeHealth $Docker

$Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10
if (
    $Health.status -ne "ok" -or
    $Health.database -ne "ok" -or
    $Health.redis -ne "ok" -or
    $Health.minio -ne "ok"
) {
    throw "API health check is degraded: $($Health | ConvertTo-Json -Compress)"
}

& $Docker compose ps
Write-Host "[xzd] Ready: http://localhost:8000/docs"
Write-Host "[xzd] MinIO: http://localhost:9001"
