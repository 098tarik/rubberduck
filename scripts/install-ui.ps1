Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ScriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ScriptRoot) -and -not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
    $ScriptRoot = Split-Path -Parent $PSCommandPath
}
if ([string]::IsNullOrWhiteSpace($ScriptRoot)) {
    $ScriptRoot = [System.AppDomain]::CurrentDomain.BaseDirectory
}
if ([string]::IsNullOrWhiteSpace($ScriptRoot)) {
    throw "Unable to determine installer script directory."
}
$ScriptRoot = $ScriptRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)

$EmbeddedInstallScript = @'
param(
    [string]$InstallRoot = (Get-Location).Path,
    [string]$PackageSource = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $InstallRoot = (Get-Location).Path
}

$Root = Resolve-Path $InstallRoot
$Venv = Join-Path $Root ".venv"

if ([string]::IsNullOrWhiteSpace($PackageSource)) {
    if (Test-Path (Join-Path $Root "pyproject.toml")) {
        $PackageSource = "$Root"
    } else {
        $PackageSource = "rubberduck"
    }
}

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
    if (Get-Command py -ErrorAction SilentlyContinue) { return @{ Exe = "py"; Args = @("-3") } }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @{ Exe = "python"; Args = @() } }
    Fail "Python 3.11+ is required. Install it from https://www.python.org/downloads/"
}

function Invoke-Python([hashtable]$PyCmd, [string[]]$Args) { & $PyCmd.Exe @($PyCmd.Args + $Args) }

function Assert-PythonVersion([hashtable]$PyCmd) {
    $version = Invoke-Python -PyCmd $PyCmd -Args @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    $parts = $version.Trim().Split(".")
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) { Fail "Python $version detected. Python 3.11+ is required." }
}

function Ensure-Ollama {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Write-Warn "Ollama is not installed. Install it from https://ollama.com/download before running chats."; return }
    try { $list = ollama list } catch { Write-Warn "Ollama is installed but not running. Start it and run 'ollama pull deepseek-r1:8b'."; return }
    if ((@($list) | Where-Object { $_.Trim() -ne "" }).Count -le 1) { Write-Warn "No Ollama models found. Pull one with: ollama pull deepseek-r1:8b" }
}

Write-Step "RubberDuck installer"
$py = Get-PythonCommand
Assert-PythonVersion -PyCmd $py
Ensure-Ollama
if (-not (Test-Path $Venv)) { Write-Step "Creating virtual environment at $Venv"; Invoke-Python -PyCmd $py -Args @("-m", "venv", $Venv) } else { Write-Step "Using existing virtual environment at $Venv" }
$venvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $venvPython)) { Fail "Virtual environment is missing python.exe at $venvPython" }
Write-Step "Upgrading pip"
& $venvPython -m pip install --upgrade pip
Write-Step "Installing RubberDuck"
& $venvPython -m pip install $PackageSource
Write-Step "Installation complete"
'@

$InstallScript = Join-Path $ScriptRoot "install.ps1"
if (Test-Path $InstallScript) {
    $Root = Resolve-Path (Join-Path $ScriptRoot "..")
} else {
    $Root = Resolve-Path $ScriptRoot
    $InstallScript = Join-Path ([System.IO.Path]::GetTempPath()) ("rubberduck-install-{0}.ps1" -f ([guid]::NewGuid().ToString("N")))
    Set-Content -Path $InstallScript -Value $EmbeddedInstallScript -Encoding UTF8
}

$steps = @("Welcome", "Prerequisites", "Install", "Finish")
$syncHash = [hashtable]::Synchronized(@{})
$syncHash.StepIndex = 0
$syncHash.InstallExitCode = $null
$syncHash.InstallRunning = $false
$syncHash.InstallProcess = $null
$syncHash.InstallEventIds = @()

function Get-PythonInfo {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $version = (& py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") 2>$null
        return @{ Found = $true; Version = $version; Command = "py -3" }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $version = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") 2>$null
        return @{ Found = $true; Version = $version; Command = "python" }
    }
    return @{ Found = $false; Version = ""; Command = "" }
}

function Test-Prerequisites {
    $python = Get-PythonInfo
    $pythonOk = $false
    if ($python.Found -and $python.Version) {
        $parts = $python.Version.Trim().Split(".")
        if ($parts.Length -ge 2) {
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            $pythonOk = ($major -gt 3) -or ($major -eq 3 -and $minor -ge 11)
        }
    }

    $ollamaInstalled = [bool](Get-Command ollama -ErrorAction SilentlyContinue)
    $ollamaRunning = $false
    $modelsAvailable = $false
    if ($ollamaInstalled) {
        try {
            $list = ollama list
            $ollamaRunning = $true
            $lines = @($list) | Where-Object { $_.Trim() -ne "" }
            $modelsAvailable = $lines.Count -gt 1
        } catch {
            $ollamaRunning = $false
        }
    }

    return @{
        PythonFound = $python.Found
        PythonVersion = $python.Version
        PythonCommand = $python.Command
        PythonOk = $pythonOk
        OllamaInstalled = $ollamaInstalled
        OllamaRunning = $ollamaRunning
        ModelsAvailable = $modelsAvailable
    }
}

function Set-StepHeader([string]$title, [string]$subtitle) {
    $syncHash.StepTitle.Text = $title
    $syncHash.SubTitle.Text = $subtitle
}

function Append-Log([string]$line) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        return
    }
    if ($syncHash.LogBox.InvokeRequired) {
        $syncHash.LogBox.BeginInvoke([Action[string]]{
            param($msg)
            $syncHash.LogBox.AppendText($msg + [Environment]::NewLine)
        }, $line) | Out-Null
    } else {
        $syncHash.LogBox.AppendText($line + [Environment]::NewLine)
    }
}

function Show-Step {
    if ($syncHash.ApplyStepUi) {
        & $syncHash.ApplyStepUi $syncHash $syncHash.StepIndex
    }
}

function Start-Install {
    if ($syncHash.InstallRunning) {
        return
    }
    $syncHash.InstallRunning = $true
    $syncHash.InstallExitCode = $null
    $syncHash.LogBox.Clear()
    $syncHash.Progress.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
    $syncHash.NextButton.Enabled = $false
    $syncHash.BackButton.Enabled = $false
    Append-Log "Starting install..."
    Append-Log "Running: powershell -ExecutionPolicy Bypass -File $InstallScript -InstallRoot $Root"
    Append-Log ""

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "powershell"
    $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$InstallScript`" -InstallRoot `"$Root`""
    $psi.WorkingDirectory = "$Root"
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $proc.EnableRaisingEvents = $true

    $eventData = @{ Sync = $syncHash }
    $outEvent = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -MessageData $eventData -Action {
        $sync = $Event.MessageData.Sync
        $line = $EventArgs.Data
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            if ($sync.LogBox.InvokeRequired) {
                $sync.LogBox.BeginInvoke([Action[string]]{
                    param($msg)
                    $sync.LogBox.AppendText($msg + [Environment]::NewLine)
                }, $line) | Out-Null
            } else {
                $sync.LogBox.AppendText($line + [Environment]::NewLine)
            }
        }
    }
    $errEvent = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -MessageData $eventData -Action {
        $sync = $Event.MessageData.Sync
        $line = $EventArgs.Data
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            $msg = "[stderr] $line"
            if ($sync.LogBox.InvokeRequired) {
                $sync.LogBox.BeginInvoke([Action[string]]{
                    param($text)
                    $sync.LogBox.AppendText($text + [Environment]::NewLine)
                }, $msg) | Out-Null
            } else {
                $sync.LogBox.AppendText($msg + [Environment]::NewLine)
            }
        }
    }
    $syncHash.InstallEventIds = @($outEvent.Id, $errEvent.Id)
    $exitEvent = Register-ObjectEvent -InputObject $proc -EventName Exited -MessageData $eventData -Action {
        $sync = $Event.MessageData.Sync
        $exitCode = $Event.Sender.ExitCode
        $sync.InstallExitCode = $exitCode
        $sync.InstallRunning = $false
        $sync.Form.BeginInvoke([Action]{
            $sync.Progress.Style = [System.Windows.Forms.ProgressBarStyle]::Blocks
            if ($sync.InstallExitCode -eq 0) {
                $sync.FinishBody.Text = "RubberDuck installed successfully." + [Environment]::NewLine + [Environment]::NewLine +
                    "You can now run:" + [Environment]::NewLine +
                    "1) .\.venv\Scripts\Activate.ps1" + [Environment]::NewLine +
                    "2) uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
            } else {
                $sync.FinishBody.Text = "Setup failed with exit code $($sync.InstallExitCode)." + [Environment]::NewLine +
                    "Review the log output and retry."
            }
            $sync.StepIndex = 3
            & $sync.ApplyStepUi $sync $sync.StepIndex
        }) | Out-Null
        foreach ($id in @($sync.InstallEventIds + $Event.SubscriptionId)) {
            Unregister-Event -SubscriptionId $id -ErrorAction SilentlyContinue
        }
        $sync.InstallEventIds = @()
    }

    $null = $proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    $syncHash.InstallProcess = $proc
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "RubberDuck Setup"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(760, 520)
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.BackColor = [System.Drawing.Color]::White

$leftPanel = New-Object System.Windows.Forms.Panel
$leftPanel.Dock = "Left"
$leftPanel.Width = 180
$leftPanel.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$form.Controls.Add($leftPanel)

$brandTitle = New-Object System.Windows.Forms.Label
$brandTitle.ForeColor = [System.Drawing.Color]::White
$brandTitle.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$brandTitle.Text = "RubberDuck"
$brandTitle.AutoSize = $true
$brandTitle.Location = New-Object System.Drawing.Point(20, 40)
$leftPanel.Controls.Add($brandTitle)

$brandSub = New-Object System.Windows.Forms.Label
$brandSub.ForeColor = [System.Drawing.Color]::White
$brandSub.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$brandSub.Text = "Setup Wizard"
$brandSub.AutoSize = $true
$brandSub.Location = New-Object System.Drawing.Point(22, 75)
$leftPanel.Controls.Add($brandSub)

$content = New-Object System.Windows.Forms.Panel
$content.Dock = "Fill"
$content.Padding = New-Object System.Windows.Forms.Padding(20, 20, 20, 70)
$form.Controls.Add($content)

$stepTitle = New-Object System.Windows.Forms.Label
$stepTitle.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$stepTitle.AutoSize = $true
$stepTitle.Location = New-Object System.Drawing.Point(20, 20)
$content.Controls.Add($stepTitle)

$subTitle = New-Object System.Windows.Forms.Label
$subTitle.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$subTitle.AutoSize = $true
$subTitle.Location = New-Object System.Drawing.Point(22, 55)
$content.Controls.Add($subTitle)

$welcomePanel = New-Object System.Windows.Forms.Panel
$welcomePanel.Location = New-Object System.Drawing.Point(20, 90)
$welcomePanel.Size = New-Object System.Drawing.Size(510, 300)
$content.Controls.Add($welcomePanel)

$welcomeBody = New-Object System.Windows.Forms.Label
$welcomeBody.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$welcomeBody.AutoSize = $false
$welcomeBody.Size = New-Object System.Drawing.Size(510, 300)
$welcomeBody.Text = "This wizard installs RubberDuck and prepares a Python virtual environment.`r`n`r`nClick Next to continue."
$welcomePanel.Controls.Add($welcomeBody)

$checkPanel = New-Object System.Windows.Forms.Panel
$checkPanel.Location = New-Object System.Drawing.Point(20, 90)
$checkPanel.Size = New-Object System.Drawing.Size(510, 300)
$checkPanel.Visible = $false
$content.Controls.Add($checkPanel)

$checkBody = New-Object System.Windows.Forms.Label
$checkBody.Font = New-Object System.Drawing.Font("Consolas", 10)
$checkBody.AutoSize = $false
$checkBody.Size = New-Object System.Drawing.Size(510, 300)
$checkPanel.Controls.Add($checkBody)

$installPanel = New-Object System.Windows.Forms.Panel
$installPanel.Location = New-Object System.Drawing.Point(20, 90)
$installPanel.Size = New-Object System.Drawing.Size(510, 300)
$installPanel.Visible = $false
$content.Controls.Add($installPanel)

$installText = New-Object System.Windows.Forms.Label
$installText.Text = "Setup will run the installer script and stream output below."
$installText.AutoSize = $true
$installText.Location = New-Object System.Drawing.Point(0, 0)
$installPanel.Controls.Add($installText)

$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Location = New-Object System.Drawing.Point(0, 25)
$progress.Size = New-Object System.Drawing.Size(510, 20)
$progress.Style = [System.Windows.Forms.ProgressBarStyle]::Blocks
$installPanel.Controls.Add($progress)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Location = New-Object System.Drawing.Point(0, 55)
$logBox.Size = New-Object System.Drawing.Size(510, 245)
$logBox.Multiline = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly = $true
$logBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$installPanel.Controls.Add($logBox)

$finishPanel = New-Object System.Windows.Forms.Panel
$finishPanel.Location = New-Object System.Drawing.Point(20, 90)
$finishPanel.Size = New-Object System.Drawing.Size(510, 300)
$finishPanel.Visible = $false
$content.Controls.Add($finishPanel)

$finishBody = New-Object System.Windows.Forms.Label
$finishBody.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$finishBody.AutoSize = $false
$finishBody.Size = New-Object System.Drawing.Size(510, 300)
$finishPanel.Controls.Add($finishBody)

$buttonBar = New-Object System.Windows.Forms.Panel
$buttonBar.Dock = "Bottom"
$buttonBar.Height = 56
$buttonBar.BackColor = [System.Drawing.Color]::FromArgb(245, 245, 245)
$form.Controls.Add($buttonBar)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = "Cancel"
$cancelButton.Size = New-Object System.Drawing.Size(90, 28)
$cancelButton.Location = New-Object System.Drawing.Point(650, 14)
$cancelButton.Anchor = "Bottom,Right"
$buttonBar.Controls.Add($cancelButton)

$nextButton = New-Object System.Windows.Forms.Button
$nextButton.Text = "Next >"
$nextButton.Size = New-Object System.Drawing.Size(90, 28)
$nextButton.Location = New-Object System.Drawing.Point(550, 14)
$nextButton.Anchor = "Bottom,Right"
$buttonBar.Controls.Add($nextButton)

$backButton = New-Object System.Windows.Forms.Button
$backButton.Text = "< Back"
$backButton.Size = New-Object System.Drawing.Size(90, 28)
$backButton.Location = New-Object System.Drawing.Point(450, 14)
$backButton.Anchor = "Bottom,Right"
$buttonBar.Controls.Add($backButton)

$syncHash.Form = $form
$syncHash.StepTitle = $stepTitle
$syncHash.SubTitle = $subTitle
$syncHash.WelcomePanel = $welcomePanel
$syncHash.CheckPanel = $checkPanel
$syncHash.InstallPanel = $installPanel
$syncHash.FinishPanel = $finishPanel
$syncHash.CheckBody = $checkBody
$syncHash.LogBox = $logBox
$syncHash.FinishBody = $finishBody
$syncHash.Progress = $progress
$syncHash.BackButton = $backButton
$syncHash.NextButton = $nextButton
$syncHash.ApplyStepUi = {
    param($sync, [int]$index)

    $sync.WelcomePanel.Visible = ($index -eq 0)
    $sync.CheckPanel.Visible = ($index -eq 1)
    $sync.InstallPanel.Visible = ($index -eq 2)
    $sync.FinishPanel.Visible = ($index -eq 3)
    $sync.BackButton.Enabled = ($index -gt 0 -and -not $sync.InstallRunning)

    switch ($index) {
        0 {
            $sync.StepTitle.Text = "Welcome to the RubberDuck Setup Wizard"
            $sync.SubTitle.Text = "This wizard installs RubberDuck on your machine."
            $sync.NextButton.Text = "Next >"
            $sync.NextButton.Enabled = $true
        }
        1 {
            $sync.StepTitle.Text = "Prerequisite Check"
            $sync.SubTitle.Text = "Setup checks required software before install."
            $result = Test-Prerequisites
            $statusLines = @(
                ("Python 3.11+: " + ($(if ($result.PythonOk) { "OK ($($result.PythonVersion))" } elseif ($result.PythonFound) { "Found $($result.PythonVersion) (needs 3.11+)" } else { "Not found" }))),
                ("Ollama installed: " + $(if ($result.OllamaInstalled) { "Yes" } else { "No" })),
                ("Ollama running: " + $(if ($result.OllamaRunning) { "Yes" } else { "No" })),
                ("Ollama model pulled: " + $(if ($result.ModelsAvailable) { "Yes" } else { "No" }))
            )
            $sync.CheckBody.Text = ($statusLines -join [Environment]::NewLine) + [Environment]::NewLine + [Environment]::NewLine +
                "Notes:" + [Environment]::NewLine +
                "- Python 3.11+ is required to continue." + [Environment]::NewLine +
                "- Ollama can be installed or configured later, but chats need it."
            $sync.NextButton.Text = "Next >"
            $sync.NextButton.Enabled = $result.PythonOk
        }
        2 {
            $sync.StepTitle.Text = "Ready to Install"
            $sync.SubTitle.Text = "Click Install to begin."
            if (-not $sync.InstallRunning -and $sync.InstallExitCode -eq $null) {
                $sync.NextButton.Text = "Install"
            }
            if ($sync.InstallRunning) {
                $sync.NextButton.Enabled = $false
                $sync.BackButton.Enabled = $false
                $sync.Progress.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
            } else {
                $sync.NextButton.Enabled = ($sync.InstallExitCode -eq $null)
                $sync.Progress.Style = [System.Windows.Forms.ProgressBarStyle]::Blocks
            }
        }
        3 {
            $sync.StepTitle.Text = "Setup Complete"
            $sync.SubTitle.Text = "RubberDuck setup has finished."
            $sync.BackButton.Enabled = $false
            $sync.NextButton.Text = "Close"
            $sync.NextButton.Enabled = $true
        }
    }
}

$backButton.Add_Click({
    if ($syncHash.InstallRunning) { return }
    if ($syncHash.StepIndex -gt 0) {
        $syncHash.StepIndex--
        Show-Step
    }
})

$nextButton.Add_Click({
    switch ($syncHash.StepIndex) {
        0 {
            $syncHash.StepIndex = 1
            Show-Step
        }
        1 {
            $syncHash.StepIndex = 2
            Show-Step
        }
        2 {
            if (-not $syncHash.InstallRunning -and $syncHash.InstallExitCode -eq $null) {
                Start-Install
                Show-Step
            }
        }
        3 {
            $form.Close()
        }
    }
})

$cancelButton.Add_Click({
    if ($syncHash.InstallRunning -and $syncHash.InstallProcess -and -not $syncHash.InstallProcess.HasExited) {
        $answer = [System.Windows.Forms.MessageBox]::Show(
            "Installation is running. Exit setup?",
            "Confirm Exit",
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Question
        )
        if ($answer -eq [System.Windows.Forms.DialogResult]::No) {
            return
        }
        try { $syncHash.InstallProcess.Kill() } catch {}
    }
    $form.Close()
})

Show-Step
[void]$form.ShowDialog()
