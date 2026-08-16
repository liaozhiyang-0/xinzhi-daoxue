$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run scripts/dev.ps1 first."
}

$env:APP_ENV = "test"
$env:DEFAULT_AGENT_PROVIDER = "mock"
$env:ALLOW_MOCK_FALLBACK = "true"

Write-Host "[xzd] Validating configuration..."
& $Python scripts/validate_config.py
if ($LASTEXITCODE -ne 0) { throw "Configuration validation failed." }

Write-Host "[xzd] Scanning tracked files for secrets..."
& $Python scripts/check_sensitive_files.py
if ($LASTEXITCODE -ne 0) { throw "Sensitive file scan failed." }

Write-Host "[xzd] Running Ruff..."
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }

Write-Host "[xzd] Running Mypy..."
& $Python -m mypy apps/api/app
if ($LASTEXITCODE -ne 0) { throw "Mypy failed." }

Write-Host "[xzd] Running Pytest with coverage..."
& $Python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }

Write-Host "[xzd] Exporting OpenAPI..."
& $Python scripts/export_openapi.py
if ($LASTEXITCODE -ne 0) { throw "OpenAPI export failed." }

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
if ($DockerCommand) {
    Write-Host "[xzd] Validating Docker Compose..."
    & $DockerCommand compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed." }
} else {
    Write-Warning "Docker not found; Docker Compose validation was skipped."
}

Write-Host "[xzd] Checking Git whitespace..."
git diff --check
if ($LASTEXITCODE -ne 0) {
    throw "git diff --check failed."
}

Write-Host "[xzd] All available checks passed."
