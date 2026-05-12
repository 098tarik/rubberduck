param(
    [string]$OutputDir = "dist",
    [string]$ModuleVersion = "1.0.17"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
    throw "This build script must be run on Windows."
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$InputFile = Join-Path $PSScriptRoot "install-ui.ps1"
if (-not (Test-Path $InputFile)) {
    throw "Missing installer UI script: $InputFile"
}

$OutputPath = Join-Path (Join-Path $Root $OutputDir) "rubberduck-setup.exe"
New-Item -Path (Split-Path -Parent $OutputPath) -ItemType Directory -Force | Out-Null

Write-Host "==> Ensuring ps2exe module ($ModuleVersion)"
$module = Get-Module -ListAvailable -Name ps2exe | Sort-Object Version -Descending | Select-Object -First 1
if (-not $module -or $module.Version -lt [Version]$ModuleVersion) {
    Install-Module -Name ps2exe -Scope CurrentUser -Force -AllowClobber -RequiredVersion $ModuleVersion
}
Import-Module ps2exe -RequiredVersion $ModuleVersion -Force

Write-Host "==> Building installer executable"
Invoke-ps2exe `
    -InputFile $InputFile `
    -OutputFile $OutputPath `
    -NoConsole `
    -Title "RubberDuck Setup" `
    -Description "RubberDuck MSI-style setup wizard" `
    -Product "RubberDuck" `
    -Company "RubberDuck" `
    -Copyright "Copyright (c) RubberDuck"

Write-Host "==> Built: $OutputPath"
