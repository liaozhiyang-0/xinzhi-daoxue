$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = $null
foreach ($Version in @("3.12", "3.11")) {
    try {
        $Python = (& py "-$Version" -c "import sys; print(sys.executable)").Trim()
        break
    } catch {
        continue
    }
}
if (-not $Python) {
    throw "Python 3.11 or 3.12 is required. Install it before continuing."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required for PostgreSQL, Redis, and MinIO."
}

if (-not (Test-Path ".venv")) {
    Write-Host "[xzd] Creating virtual environment..."
    & $Python -m venv .venv
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
Write-Host "[xzd] Installing dependencies..."
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e "apps/api[dev]"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Warning "Created .env from .env.example. Change development passwords."
}

function Get-DotEnvValue([string]$Name) {
    $Line = Get-Content ".env" | Where-Object {
        $_ -match "^\s*$([regex]::Escape($Name))="
    } | Select-Object -First 1
    if (-not $Line) { return $null }
    return ($Line -split "=", 2)[1].Trim()
}

$HostDatabaseUrl = Get-DotEnvValue "HOST_DATABASE_URL"
$HostRedisUrl = Get-DotEnvValue "HOST_REDIS_URL"
$HostMinioEndpoint = Get-DotEnvValue "HOST_MINIO_ENDPOINT"
if ($HostDatabaseUrl) { $env:DATABASE_URL = $HostDatabaseUrl }
if ($HostRedisUrl) { $env:REDIS_URL = $HostRedisUrl }
if ($HostMinioEndpoint) { $env:MINIO_ENDPOINT = $HostMinioEndpoint }

Write-Host "[xzd] Starting PostgreSQL, Redis, and MinIO..."
docker compose up -d postgres redis minio

Write-Host "[xzd] Applying database migrations..."
Push-Location "apps/api"
try {
    & $VenvPython -m alembic upgrade head
} finally {
    Pop-Location
}

Write-Host "[xzd] Starting FastAPI at http://localhost:8000 ..."
& $VenvPython -m uvicorn app.main:app --app-dir apps/api --reload --host 0.0.0.0 --port 8000
