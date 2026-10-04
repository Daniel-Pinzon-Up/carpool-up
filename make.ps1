# Equivalente del Makefile para Windows sin make.
# Uso: .\make.ps1 up | down | logs | ps | migrate | seed | test | test-backend | test-frontend | lint | build | osrm | clean
param([Parameter(Position = 0)][string]$Target = 'help')

# Docker y npm escriben progreso en stderr; en Windows PowerShell 5.1 'Stop' lo convierte en error.
# Los fallos se detectan con $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

$Compose = @('compose', '--env-file', '.env', '-f', 'infra/docker-compose.yml', '-f', 'infra/docker-compose.dev.yml')
$TestDb = 'export DATABASE_URL=${DATABASE_URL%/*}/carpool_test && alembic upgrade head && pytest --cov=app --cov-report=term-missing'

function Invoke-Compose([string[]]$CommandArgs) {
    & docker @Compose @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($CommandArgs -join ' ') fallo con codigo $LASTEXITCODE" }
}

function Ensure-Env {
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
}

function Test-Frontend {
    Push-Location frontend
    try {
        npm ci
        npx ng test --watch=false
        if ($LASTEXITCODE -ne 0) { throw 'Pruebas de frontend fallaron' }
    } finally { Pop-Location }
}

switch ($Target) {
    'up' {
        Ensure-Env
        Invoke-Compose @('up', '-d', '--build')
        Write-Host 'Web: https://localhost  API: http://localhost:8000/api/v1/docs  Correo: http://localhost:8025'
    }
    'down' { Invoke-Compose @('down') }
    'logs' { Invoke-Compose @('logs', '-f', '--tail=100') }
    'ps' { Invoke-Compose @('ps') }
    'migrate' { Invoke-Compose @('exec', 'api', 'alembic', 'upgrade', 'head') }
    'seed' { Invoke-Compose @('exec', 'api', 'python', '-m', 'app.seed') }
    'test-backend' {
        Ensure-Env
        Invoke-Compose @('up', '-d', 'db', 'redis')
        Invoke-Compose @('run', '--rm', '--no-deps', 'api', 'sh', '-c', $TestDb)
    }
    'test-frontend' { Test-Frontend }
    'test' {
        Ensure-Env
        Invoke-Compose @('up', '-d', 'db', 'redis')
        Invoke-Compose @('run', '--rm', '--no-deps', 'api', 'sh', '-c', $TestDb)
        Test-Frontend
    }
    'lint' {
        Invoke-Compose @('run', '--rm', '--no-deps', 'api', 'sh', '-c', 'ruff check . && ruff format --check . && mypy app')
        Push-Location frontend
        try { npx ng lint; npx prettier --check 'src/**/*.{ts,html,css}' } finally { Pop-Location }
    }
    'build' { Invoke-Compose @('build') }
    'osrm' { & bash infra/scripts/build_osrm.sh }
    'clean' { Invoke-Compose @('down', '-v') }
    default {
        Write-Host 'Objetivos: up, down, logs, ps, migrate, seed, test, test-backend, test-frontend, lint, build, osrm, clean'
    }
}
