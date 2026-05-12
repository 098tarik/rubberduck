Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Venv = Join-Path $Root ".venv"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Write-Warn([string]$Message) {
    Write-Host ""
    Write-Host "[warning] $Message" -ForegroundColor Yellow
}

function Fail([string]$Message) {
    throw "[error] $Message"
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{
            Exe  = "py"
            Args = @("-3")
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{
            Exe  = "python"
            Args = @()
        }
    }
    Fail "Python 3.11+ is required. Install it from https://www.python.org/downloads/"
}

function Invoke-Python([hashtable]$PyCmd, [string[]]$Args) {
    & $PyCmd.Exe @($PyCmd.Args + $Args)
}

function Assert-PythonVersion([hashtable]$PyCmd) {
    $version = Invoke-Python -PyCmd $PyCmd -Args @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    $parts = $version.Trim().Split(".")
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
        Fail "Python $version detected. Python 3.11+ is required."
    }
}

function Ensure-Ollama {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Warn "Ollama is not installed. Install it from https://ollama.com/download before running chats."
        return
    }
    try {
        $list = ollama list
    } catch {
        Write-Warn "Ollama is installed but not running. Start it and run 'ollama pull deepseek-r1:8b'."
        return
    }
    $lines = @($list) | Where-Object { $_.Trim() -ne "" }
    if ($lines.Count -le 1) {
        Write-Warn "No Ollama models found. Pull one with: ollama pull deepseek-r1:8b"
    }
}

Write-Step "RubberDuck installer"
$py = Get-PythonCommand
Assert-PythonVersion -PyCmd $py
Ensure-Ollama

if (-not (Test-Path $Venv)) {
    Write-Step "Creating virtual environment at $Venv"
    Invoke-Python -PyCmd $py -Args @("-m", "venv", $Venv)
} else {
    Write-Step "Using existing virtual environment at $Venv"
}

$venvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Fail "Virtual environment is missing python.exe at $venvPython"
}

Write-Step "Upgrading pip"
& $venvPython -m pip install --upgrade pip

Write-Step "Installing RubberDuck"
Push-Location $Root
try {
    & $venvPython -m pip install .
} finally {
    Pop-Location
}

Write-Step "Installation complete"
Write-Host @"
Next steps:
1) Activate the virtualenv:
   .\.venv\Scripts\Activate.ps1
2) Start the app:
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
3) Open:
   http://localhost:8000
"@
