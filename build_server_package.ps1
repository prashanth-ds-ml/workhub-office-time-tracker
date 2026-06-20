$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleaseDir = Join-Path $ProjectRoot "release"
$PackageDir = Join-Path $ReleaseDir "WorkHub-Server"
$ZipPath = Join-Path $ReleaseDir "WorkHub-Server.zip"

if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

$Files = @(
    "app.py",
    "storage.py",
    "requirements.txt",
    "run_production_server.ps1",
    "migrate_json_to_mongodb.py",
    "reset_workhub_data.py",
    "Dockerfile",
    "docker-compose.yml",
    "render.yaml",
    "RENDER_DEPLOYMENT.md",
    ".env.production.example",
    ".env.docker.example",
    "DISTRIBUTION.md"
)
foreach ($File in $Files) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $File) -Destination $PackageDir
}

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipPath

Write-Host "Server package created:"
Write-Host "  $ZipPath"
