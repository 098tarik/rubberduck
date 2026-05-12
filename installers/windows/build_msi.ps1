param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command '$Name'. Install it and retry."
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")

Write-Host "[1/6] Checking prerequisites..."
Require-Command "python"
Require-Command "candle"
Require-Command "light"
Require-Command "heat"

$BuildDir = Join-Path $ScriptDir "build"
$DistDir = Join-Path $ScriptDir "dist"
$VenvDir = Join-Path $ScriptDir ".venv-build"
$PyDistDir = Join-Path $RepoRoot "dist\RubberDuckServer"
$RuntimeRepoDir = Join-Path $PyDistDir "repo"
$ProductWxs = Join-Path $ScriptDir "Product.wxs"
$HarvestWxs = Join-Path $ScriptDir "AppFiles.wxs"

Write-Host "[2/6] Preparing build virtual environment..."
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
}

$Py = Join-Path $VenvDir "Scripts\python.exe"
$Pip = Join-Path $VenvDir "Scripts\pip.exe"

& $Py -m pip install --upgrade pip
& $Py -m pip install pyinstaller
& $Py -m pip install -e $RepoRoot

Write-Host "[3/7] Building RubberDuckServer.exe with PyInstaller..."
if (Test-Path (Join-Path $RepoRoot "build")) { Remove-Item (Join-Path $RepoRoot "build") -Recurse -Force }
if (Test-Path (Join-Path $RepoRoot "dist")) { Remove-Item (Join-Path $RepoRoot "dist") -Recurse -Force }

& $Py -m PyInstaller `
    --clean `
    --noconfirm `
    --onedir `
    --name RubberDuckServer `
    --collect-all uvicorn `
    --collect-all fastapi `
    --collect-all starlette `
    --collect-all pydantic `
    --add-data "$RepoRoot\index.html;." `
    --add-data "$RepoRoot\assets;assets" `
    "$ScriptDir\rubberduck_server.py"

if (-not (Test-Path $PyDistDir)) {
    throw "PyInstaller output not found at $PyDistDir"
}

Write-Host "[4/7] Bundling repository runtime payload..."
if (Test-Path $RuntimeRepoDir) { Remove-Item $RuntimeRepoDir -Recurse -Force }
New-Item -ItemType Directory -Path $RuntimeRepoDir | Out-Null

# Include project files so installed app has a complete local runtime snapshot.
robocopy $RepoRoot $RuntimeRepoDir /E /NFL /NDL /NJH /NJS /NP `
  /XD ".git" ".github" ".venv" "venv" "node_modules" "dist" "build" "__pycache__" "installers\windows\build" "installers\windows\dist" "installers\windows\.venv-build"

if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed while creating runtime payload (exit code $LASTEXITCODE)"
}

Write-Host "[5/7] Harvesting files for WiX..."
if (-not (Test-Path $BuildDir)) { New-Item -ItemType Directory -Path $BuildDir | Out-Null }
if (-not (Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir | Out-Null }

heat dir $PyDistDir `
    -nologo `
    -gg `
    -scom `
    -sreg `
    -srd `
    -dr INSTALLFOLDER `
    -cg AppFiles `
    -var var.SourceDir `
    -out $HarvestWxs

Write-Host "[6/7] Compiling WiX sources..."
$ProductObj = Join-Path $BuildDir "Product.wixobj"
$AppFilesObj = Join-Path $BuildDir "AppFiles.wixobj"

candle -nologo -dSourceDir="$PyDistDir" -dProductVersion="$Version" -out $ProductObj $ProductWxs
candle -nologo -dSourceDir="$PyDistDir" -out $AppFilesObj $HarvestWxs

Write-Host "[7/7] Linking MSI..."
$MsiPath = Join-Path $DistDir "RubberDuck-$Version.msi"
light -nologo -ext WixUIExtension -out $MsiPath $ProductObj $AppFilesObj

Write-Host "Done. MSI created at: $MsiPath"
