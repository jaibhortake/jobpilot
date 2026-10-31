# Full check (T4): both segments' tests and static gates, then the browser tests.
# Works in PowerShell 7 (pwsh) and Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:UV_NATIVE_TLS = '1'               # use the Windows certificate store (corporate TLS inspection)
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue

function Step([string]$name, [scriptblock]$cmd) {
  Write-Host "`n=== $name" -ForegroundColor Cyan
  & $cmd
  if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $name" -ForegroundColor Red; exit 1 }
}

$watch = [Diagnostics.Stopwatch]::StartNew()

Push-Location (Join-Path $root 'jobpilot-backend')
try {
  Step 'backend: pytest'  { uv run pytest -q }
  Step 'backend: ruff'    { uv run ruff check src tests main.py }
  Step 'backend: mypy'    { uv run mypy src tests }
  Step 'backend: browser tests' { uv run pytest -q -m browser --no-header; if ($LASTEXITCODE -eq 5) { $global:LASTEXITCODE = 0 } }  # 5 = none collected yet
} finally { Pop-Location }

Push-Location (Join-Path $root 'jobpilot-frontend')
try {
  Step 'frontend: vitest' { npm run test --silent }
  Step 'frontend: lint'   { npm run lint --silent }
  Step 'frontend: tsc'    { npx tsc -b }
  Step 'frontend: build'  { npm run build --silent }
} finally { Pop-Location }

Write-Host ("`nALL CHECKS PASSED in {0:N0}s" -f $watch.Elapsed.TotalSeconds) -ForegroundColor Green
