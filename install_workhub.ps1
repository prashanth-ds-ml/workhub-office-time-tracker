param(
    [string]$ApiUrl = "https://workhub-api-u07x.onrender.com",
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadDir = Join-Path $SourceDir "WorkHub"
$InstallDir = Join-Path $env:LOCALAPPDATA "WorkHubApp"

if (-not (Test-Path (Join-Path $PayloadDir "WorkHub.exe"))) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "The WorkHub application files are missing. Extract the complete WorkHub-Installer.zip archive, then run Install WorkHub.bat again.",
        "WorkHub installation",
        "OK",
        "Error"
    ) | Out-Null
    exit 1
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -Path (Join-Path $PayloadDir "*") -Destination $InstallDir -Recurse -Force

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

$AppExecutable = Join-Path $InstallDir "WorkHub.exe"
$Shell = New-Object -ComObject WScript.Shell

$DesktopShortcut = $Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "WorkHub.lnk"))
$DesktopShortcut.TargetPath = $AppExecutable
$DesktopShortcut.WorkingDirectory = $InstallDir
$DesktopShortcut.Description = "WorkHub Office Time Tracker"
$DesktopShortcut.Save()

$Programs = [Environment]::GetFolderPath("Programs")
$StartMenuShortcut = $Shell.CreateShortcut((Join-Path $Programs "WorkHub.lnk"))
$StartMenuShortcut.TargetPath = $AppExecutable
$StartMenuShortcut.WorkingDirectory = $InstallDir
$StartMenuShortcut.Description = "WorkHub Office Time Tracker"
$StartMenuShortcut.Save()

if (-not $NoLaunch) {
    Start-Process -FilePath $AppExecutable
}

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
    "WorkHub and all required runtime dependencies were installed successfully. Python is not required. Shortcuts were added to the Desktop and Start menu.",
    "WorkHub installation",
    "OK",
    "Information"
) | Out-Null
