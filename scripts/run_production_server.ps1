param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "app.py")) {
    $PSScriptRoot
} else {
    Resolve-Path (Join-Path $PSScriptRoot "..")
}
Set-Location $ProjectRoot

if (-not $env:WORKHUB_ENV) { $env:WORKHUB_ENV = "production" }
if (-not $env:MONGO_URI) { throw "MONGO_URI is required" }
if (-not $env:MONGO_DB) { $env:MONGO_DB = "workhub" }
if (-not $env:WORKHUB_JWT_SECRET) { throw "WORKHUB_JWT_SECRET is required" }
if (-not $env:WORKHUB_BOOTSTRAP_SECRET) { throw "WORKHUB_BOOTSTRAP_SECRET is required" }

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
    & ".venv\Scripts\python.exe" -m pip install -r requirements.txt
}

& ".venv\Scripts\python.exe" -m uvicorn app:app --host $BindHost --port $Port
