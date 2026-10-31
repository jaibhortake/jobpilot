# Starts the backend (http://127.0.0.1:8000) and the frontend (http://localhost:5173), each in its own window.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { 'pwsh' } else { 'powershell' }
$prep = "`$env:UV_NATIVE_TLS='1'; Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue;"

Start-Process $shell -ArgumentList '-NoExit', '-Command', "$prep Set-Location '$root\jobpilot-backend'; uv run python main.py"
Start-Process $shell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\jobpilot-frontend'; npm run dev"
Write-Host 'Backend: http://127.0.0.1:8000/api/health   Frontend: http://localhost:5173'
