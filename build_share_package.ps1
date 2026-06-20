$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ReleaseDir = Join-Path $ProjectRoot "release"
$PackageDir = Join-Path $ReleaseDir "WorkHub-Installer"
$ZipPath = Join-Path $ReleaseDir "WorkHub-Installer.zip"

if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

if (Test-Path $VenvPython) {
    & $VenvPython (Join-Path $ProjectRoot "integration_smoke.py")
} else {
    python (Join-Path $ProjectRoot "integration_smoke.py")
}

$Files = @(
    "app.py",
    "admin_panel.py",
    "desktop_app.py",
    "storage.py",
    "requirements.txt",
    "install_workhub.ps1",
    "Install WorkHub.bat",
    "DISTRIBUTION.md"
)
foreach ($File in $Files) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $File) -Destination $PackageDir
}

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipPath

Write-Host "Shareable installer created:"
Write-Host "  $ZipPath"
