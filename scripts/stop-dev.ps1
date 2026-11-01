$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogPath = Join-Path $ProjectRoot '.logs'
$StatePath = Join-Path $LogPath 'processes.json'
$BackendPython = Join-Path $ProjectRoot 'backend\.venv\Scripts\python.exe'
$ViteScript = Join-Path $ProjectRoot 'frontend\node_modules\vite\bin\vite.js'
$Processes = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (($_.Name -eq 'python.exe' -and $_.CommandLine.Contains($BackendPython)) -or ($_.Name -eq 'node.exe' -and $_.CommandLine.Contains($ViteScript)))
}
foreach ($ProcessInfo in $Processes) {
    Stop-Process -Id $ProcessInfo.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped ProcureFlow process $($ProcessInfo.ProcessId)."
}
if (Test-Path -LiteralPath $StatePath) { Remove-Item -LiteralPath $StatePath -Force }
Write-Host 'The local SQLite database and logs were kept.'
