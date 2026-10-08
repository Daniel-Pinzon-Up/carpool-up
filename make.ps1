# Equivalente del Makefile para Windows sin make.
# Uso: .\make.ps1 token <correo> | email-test <correo> | up | down | logs | ps | migrate | seed | e2e-users | test | test-backend | test-frontend | test-e2e | lint | build | osrm | tiles | backup-check | restore <archivo> | clean
param(
    [Parameter(Position = 0)][string]$Target = 'help',
    [Parameter(Position = 1)][string]$Email = ''
)

# Docker y npm escriben progreso en stderr; en Windows PowerShell 5.1 'Stop' lo convierte en error.
# Los fallos se detectan con $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

$Compose = @('compose', '--env-file', '.env', '-f', 'infra/docker-compose.yml', '-f', 'infra/docker-compose.dev.yml')
# OSRM arranca solo cuando ya existen sus datos (.\make.ps1 osrm).
if (Test-Path 'infra/osrm/data/pamplona.osrm.mldgr') { $Compose += @('--profile', 'osrm') }
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
    'token' { Invoke-Compose @('exec', 'api', 'python', '-m', 'app.cli', 'token', $Email) }
    'email-test' { Invoke-Compose @('exec', '-T', 'worker', 'python', '-m', 'app.cli', 'email-test', $Email) }
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
    'tiles' { & bash infra/scripts/build_tiles.sh }
    'e2e-users' {
        New-Item -ItemType Directory -Force 'frontend/e2e/.auth' | Out-Null
        & docker @Compose exec -T api python -m app.cli e2e-users | Out-File -Encoding ascii 'frontend/e2e/.auth/credentials.json'
        Write-Host 'Cuentas E2E listas (credenciales en frontend/e2e/.auth, ignorado por git)'
    }
    'test-e2e' { Push-Location frontend; npx playwright test; Pop-Location }
    'backup-check' { Invoke-Compose @('exec', 'backup', 'sh', '/restore.sh') }
    'restore' {
        Invoke-Compose @('stop', 'api', 'worker')
        Invoke-Compose @('exec', 'backup', 'sh', '/restore.sh', $Email, 'live')
        Invoke-Compose @('start', 'api', 'worker')
    }
    'clean' { Invoke-Compose @('down', '-v') }
    default {
        Write-Host 'Objetivos: up, down, logs, ps, migrate, seed, token <correo>, e2e-users, test, test-backend, test-frontend, test-e2e, lint, build, osrm, tiles, backup-check, restore <archivo>, clean'
    }
}
