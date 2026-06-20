$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".venv\Scripts\python.exe" -m pip install "pyinstaller==6.14.1"
& ".venv\Scripts\python.exe" integration_smoke.py
& ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean WorkHub.spec

$ReleaseDir = Join-Path $ProjectRoot "release"
$PackageDir = Join-Path $ReleaseDir "WorkHub"
$ZipPath = Join-Path $ReleaseDir "WorkHub-Windows.zip"

if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
Copy-Item -Path "dist\WorkHub\*" -Destination $PackageDir -Recurse -Force
Copy-Item -LiteralPath "DISTRIBUTION.md" -Destination $PackageDir

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipPath

Write-Host ""
Write-Host "Release created:"
Write-Host "  $PackageDir\WorkHub.exe"
Write-Host "  $ZipPath"
