param(
    [string]$ApiUrl = ""
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "WorkHubApp"
$Python = Get-Command python -ErrorAction SilentlyContinue

if (-not $Python) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Python 3.10 or newer is required. Install Python from python.org, enable 'Add Python to PATH', then run this installer again.",
        "WorkHub installation",
        "OK",
        "Error"
    ) | Out-Null
    exit 1
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$Files = @(
    "app.py",
    "admin_panel.py",
    "desktop_app.py",
    "storage.py",
    "requirements.txt"
)
foreach ($File in $Files) {
    Copy-Item -LiteralPath (Join-Path $SourceDir $File) -Destination $InstallDir -Force
}

if (-not (Test-Path (Join-Path $InstallDir ".venv\Scripts\pythonw.exe"))) {
    & python -m venv (Join-Path $InstallDir ".venv")
}

$VenvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $InstallDir "requirements.txt")

if (-not $ApiUrl) {
    $ApiUrl = Read-Host "Enter the shared WorkHub API URL (example: https://workhub.company.com). Leave blank for local-only mode"
}
$ApiUrl = $ApiUrl.Trim().TrimEnd("/")
if ($ApiUrl -and $ApiUrl -notmatch '^https://') {
    throw "The shared WorkHub API URL must start with https://"
}
$ClientDataDir = Join-Path $env:LOCALAPPDATA "WorkHub"
New-Item -ItemType Directory -Path $ClientDataDir -Force | Out-Null
$ClientConfig = @{
    api_url = $ApiUrl
} | ConvertTo-Json
$ConfigPath = Join-Path $ClientDataDir "client_config.json"
[System.IO.File]::WriteAllText(
    $ConfigPath,
    $ClientConfig,
    [System.Text.UTF8Encoding]::new($false)
)

$Pythonw = Join-Path $InstallDir ".venv\Scripts\pythonw.exe"
$AppScript = Join-Path $InstallDir "desktop_app.py"
$Shell = New-Object -ComObject WScript.Shell

$DesktopShortcut = $Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "WorkHub.lnk"))
$DesktopShortcut.TargetPath = $Pythonw
$DesktopShortcut.Arguments = "`"$AppScript`""
$DesktopShortcut.WorkingDirectory = $InstallDir
$DesktopShortcut.Description = "WorkHub Office Time Tracker"
$DesktopShortcut.Save()

$Programs = [Environment]::GetFolderPath("Programs")
$StartMenuShortcut = $Shell.CreateShortcut((Join-Path $Programs "WorkHub.lnk"))
$StartMenuShortcut.TargetPath = $Pythonw
$StartMenuShortcut.Arguments = "`"$AppScript`""
$StartMenuShortcut.WorkingDirectory = $InstallDir
$StartMenuShortcut.Description = "WorkHub Office Time Tracker"
$StartMenuShortcut.Save()

Start-Process -FilePath $Pythonw -ArgumentList "`"$AppScript`""

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
    "WorkHub was installed successfully. A shortcut was added to the Desktop and Start menu.",
    "WorkHub installation",
    "OK",
    "Information"
) | Out-Null
