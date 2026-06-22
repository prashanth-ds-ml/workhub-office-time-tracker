$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleaseDir = Join-Path $ProjectRoot "release"
$PackageDir = Join-Path $ReleaseDir "WorkHub-Installer"
$ZipPath = Join-Path $ReleaseDir "WorkHub-Installer.zip"

& (Join-Path $ProjectRoot "build_release.ps1")

if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

$Files = @(
    "install_workhub.ps1",
    "Install WorkHub.bat",
    "DISTRIBUTION.md"
)
foreach ($File in $Files) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $File) -Destination $PackageDir
}
Copy-Item -LiteralPath (Join-Path $ReleaseDir "WorkHub") -Destination $PackageDir -Recurse

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipPath

Write-Host "Shareable installer created:"
Write-Host "  $ZipPath"
