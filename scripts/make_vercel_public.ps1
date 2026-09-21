param(
    [switch]$OpenSettings,
    [string]$Scope = "popuu",
    [string]$Token = $env:VERCEL_TOKEN
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$projectFile = Join-Path $repoRoot ".vercel\project.json"

if (-not (Test-Path -LiteralPath $projectFile)) {
    throw "No .vercel\project.json found. Run this from a Vercel-linked project."
}

$project = Get-Content -LiteralPath $projectFile -Raw | ConvertFrom-Json
$projectName = $project.projectName
$projectId = $project.projectId
$orgId = $project.orgId

$dashboardUrl = "https://vercel.com/$Scope/$projectName/settings/deployment-protection"

Write-Host "Project: $projectName"
Write-Host "Project ID: $projectId"
Write-Host "Org/Team ID: $orgId"
Write-Host "Dashboard scope: $Scope"
Write-Host ""
Write-Host "Deployment Protection settings:"
Write-Host $dashboardUrl
Write-Host ""

if ($OpenSettings) {
    Start-Process -FilePath $dashboardUrl
}

if ([string]::IsNullOrWhiteSpace($Token)) {
    Write-Host "No VERCEL_TOKEN found, so I cannot change the private Vercel setting from the terminal."
    Write-Host "Create one here, then rerun with:"
    Write-Host "  `$env:VERCEL_TOKEN='YOUR_TOKEN'; .\scripts\make_vercel_public.ps1"
    Write-Host "Token page: https://vercel.com/account/settings/tokens"
    exit 2
}

$headers = @{
    Authorization = "Bearer $Token"
    "Content-Type" = "application/json"
}

$projectApiUrl = "https://api.vercel.com/v9/projects/$projectId?teamId=$orgId"

Write-Host "Checking project access with Vercel API..."
$current = Invoke-RestMethod -Method Get -Uri $projectApiUrl -Headers $headers

Write-Host "API access OK for: $($current.name)"
Write-Host ""
Write-Host "Vercel does not expose a stable public CLI switch for Deployment Protection in this repo."
Write-Host "Use the settings URL above and set Protection to None / disable Vercel Authentication."
Write-Host "If the page still shows login for visitors, make sure you share the Production domain, not a Preview URL."
