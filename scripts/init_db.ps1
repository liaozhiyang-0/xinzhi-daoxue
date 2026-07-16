$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run scripts/dev.ps1 first."
}
if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
    throw ".env not found. Copy .env.example to .env first."
}

$HostDatabaseLine = Get-Content (Join-Path $RepoRoot ".env") | Where-Object {
    $_ -match "^\s*HOST_DATABASE_URL="
} | Select-Object -First 1
if ($HostDatabaseLine) {
    $env:DATABASE_URL = ($HostDatabaseLine -split "=", 2)[1].Trim()
}

Push-Location (Join-Path $RepoRoot "apps/api")
try {
    & $Python -m alembic upgrade head
} finally {
    Pop-Location
}
