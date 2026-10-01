$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install "pyinstaller==6.22.3"
& ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --onefile --windowed `
    --name WorkHubReminder `
    --distpath dist_reminder --workpath build_reminder --specpath build_reminder `
    scripts\reminder_daemon.py

$ReleaseDir = Join-Path $ProjectRoot "release"
$PackageDir = Join-Path $ReleaseDir "WorkHubReminder"
$ZipPath = Join-Path $ReleaseDir "WorkHubReminder.zip"

if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
Copy-Item -LiteralPath "dist_reminder\WorkHubReminder.exe" -Destination $PackageDir
Copy-Item -LiteralPath "scripts\WorkHubReminder-README.txt" -Destination (Join-Path $PackageDir "README.txt")
Copy-Item -LiteralPath "scripts\WorkHubReminder-Uninstall.bat" -Destination (Join-Path $PackageDir "Uninstall.bat")
Copy-Item -LiteralPath "WorkHub Setup Guide.md" -Destination (Join-Path $PackageDir "WorkHub Setup Guide.md")

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipPath

# SHA-256 of the exe, so IT can allow-list the exact file if antivirus flags it.
$ExeHash = (Get-FileHash -Algorithm SHA256 (Join-Path $PackageDir "WorkHubReminder.exe")).Hash
"WorkHubReminder.exe SHA-256: $ExeHash" | Set-Content (Join-Path $ReleaseDir "WorkHubReminder.sha256.txt")

Write-Host ""
Write-Host "Reminder package created:"
Write-Host "  $PackageDir\WorkHubReminder.exe"
Write-Host "  $ZipPath  <- send this to employees"
