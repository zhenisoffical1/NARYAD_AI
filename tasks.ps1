<#
.SYNOPSIS
  Команды проекта для Windows (аналог Makefile).

.EXAMPLE
  .\tasks.ps1 setup     # venv + зависимости бэкенда и фронтенда
  .\tasks.ps1 dev       # бэкенд на SQLite + фронтенд, без Docker
  .\tasks.ps1 test
  .\tasks.ps1 lint
  .\tasks.ps1 seed
  .\tasks.ps1 up        # docker compose (если установлен Docker Desktop)
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'dev', 'migrate', 'seed', 'test', 'lint', 'fmt', 'ai-eval', 'e2e', 'up', 'down')]
    [string]$Task = 'dev'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Py = Join-Path $Root 'backend\.venv\Scripts\python.exe'

function Invoke-Backend([string[]]$PyArgs) {
    Push-Location (Join-Path $Root 'backend')
    try { & $Py @PyArgs; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
}

function Invoke-Frontend([string[]]$NpmArgs) {
    Push-Location (Join-Path $Root 'frontend')
    try { & npm @NpmArgs; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
}

function Initialize-Env {
    $envFile = Join-Path $Root '.env'
    if (-not (Test-Path $envFile)) {
        (Get-Content (Join-Path $Root '.env.example')) `
            -replace '^DATABASE_URL=.*', 'DATABASE_URL=sqlite+aiosqlite:///./naryad.db' |
            Set-Content -Encoding utf8 $envFile
        Write-Host 'Создан .env для локального запуска на SQLite'
    }
}

switch ($Task) {
    'setup' {
        if (-not (Test-Path $Py)) { py -3 -m venv (Join-Path $Root 'backend\.venv') }
        Invoke-Backend @('-m', 'pip', 'install', '-e', '.[dev]')
        Invoke-Frontend @('install')
        Initialize-Env
    }
    'migrate' { Invoke-Backend @('-m', 'alembic', 'upgrade', 'head') }
    'seed' { Invoke-Backend @('-m', 'seed') }
    'dev' {
        Initialize-Env
        Invoke-Backend @('-m', 'alembic', 'upgrade', 'head')
        $backend = Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $Root 'backend') `
            -FilePath $Py -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', '8000', '--reload', '--reload-dir', 'app'
        try { Invoke-Frontend @('run', 'dev') } finally { Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue }
    }
    'test' {
        Invoke-Backend @('-m', 'pytest')
        Invoke-Frontend @('run', 'typecheck')
    }
    'lint' {
        Invoke-Backend @('-m', 'ruff', 'check', '.')
        Invoke-Backend @('-m', 'ruff', 'format', '--check', '.')
        Invoke-Backend @('-m', 'mypy', 'app', 'seed')
        Invoke-Frontend @('run', 'lint')
    }
    'fmt' {
        Invoke-Backend @('-m', 'ruff', 'check', '--fix', '.')
        Invoke-Backend @('-m', 'ruff', 'format', '.')
    }
    'ai-eval' { Invoke-Backend @('-m', 'tests.ai_eval') }
    'e2e' { Invoke-Frontend @('run', 'e2e') }
    'up' { docker compose up -d --build }
    'down' { docker compose down }
}
