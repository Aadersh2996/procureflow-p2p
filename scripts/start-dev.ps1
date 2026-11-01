$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot 'backend'
$FrontendPath = Join-Path $ProjectRoot 'frontend'
$LogPath = Join-Path $ProjectRoot '.logs'
$PythonPath = Join-Path $BackendPath '.venv\Scripts\python.exe'
$NodeCommand = Get-Command node.exe -ErrorAction Stop
$NodePath = $NodeCommand.Source
$NpmCommand = Get-Command npm.cmd -ErrorAction Stop
New-Item -ItemType Directory -Force -Path $LogPath | Out-Null
$OccupiedPorts = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in @(8000, 5173) -and $_.OwningProcess -gt 0 }
if ($OccupiedPorts) { throw 'A local service already occupies port 8000 or 5173. Run scripts\stop-dev.ps1 first, or close the other service.' }

if (-not (Test-Path -LiteralPath $PythonPath)) {
    Write-Host 'Creating backend virtual environment…'
    & python -m venv (Join-Path $BackendPath '.venv')
}
Write-Host 'Installing backend dependencies in backend\.venv…'
& $PythonPath -m pip install -r (Join-Path $BackendPath 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Push-Location $BackendPath
try {
    & $PythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migrations failed.' }
    & $PythonPath -m app.seed
    if ($LASTEXITCODE -ne 0) { throw 'Demo data seeding failed.' }
} finally { Pop-Location }

if (-not (Test-Path -LiteralPath (Join-Path $FrontendPath 'node_modules'))) {
    Write-Host 'Installing frontend dependencies from package-lock.json…'
    Push-Location $FrontendPath
    try { & $NpmCommand.Source ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } } finally { Pop-Location }
}

$ApiProcess = Start-Process -FilePath $PythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $BackendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogPath 'backend.log') -RedirectStandardError (Join-Path $LogPath 'backend-error.log')
$VitePath = Join-Path $FrontendPath 'node_modules\vite\bin\vite.js'
$WebProcess = Start-Process -FilePath $NodePath -ArgumentList @('"' + $VitePath + '"', '--host', '127.0.0.1') -WorkingDirectory $FrontendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogPath 'frontend.log') -RedirectStandardError (Join-Path $LogPath 'frontend-error.log')
@{ backendPid = $ApiProcess.Id; frontendPid = $WebProcess.Id; projectRoot = $ProjectRoot } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LogPath 'processes.json') -Encoding utf8

$ApiReady = $false
$WebReady = $false
for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; $ApiReady = $true } catch { Start-Sleep -Milliseconds 700 }
    try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2; $WebReady = $true } catch { Start-Sleep -Milliseconds 500 }
    if ($ApiReady -and $WebReady) { break }
}
if (-not $ApiReady -or -not $WebReady) { throw "The application did not become ready. API: $ApiReady; frontend: $WebReady. Check logs under $LogPath" }
Write-Host 'ProcureFlow is running locally:'
Write-Host '  Frontend: http://127.0.0.1:5173'
Write-Host '  API docs: http://127.0.0.1:8000/docs'
Write-Host "  Logs:     $LogPath"
