$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot 'backend'
$StatePath = Join-Path (Join-Path $ProjectRoot '.logs') 'processes.json'
if (Test-Path -LiteralPath $StatePath) { throw 'Stop the local application with scripts\stop-dev.ps1 before resetting demo data.' }
$PythonPath = Join-Path $BackendPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Backend virtual environment is missing. Run scripts\start-dev.ps1 once first.' }
Push-Location $BackendPath
try {
    & $PythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migrations failed.' }
    & $PythonPath -m app.seed --reset
    if ($LASTEXITCODE -ne 0) { throw 'Demo data reset failed.' }
} finally { Pop-Location }
