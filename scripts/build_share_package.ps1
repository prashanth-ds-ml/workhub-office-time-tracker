$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReleaseDir = Join-Path $ProjectRoot "release"
$PackageDir = Join-Path $ReleaseDir "WorkHub-Installer"
$ZipPath = Join-Path $ReleaseDir "WorkHub-Installer.zip"

& (Join-Path $PSScriptRoot "build_release.ps1")

if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

$Files = @(
    "scripts\install_workhub.ps1",
    "scripts\Install WorkHub.bat",
    "docs\DISTRIBUTION.md"
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
