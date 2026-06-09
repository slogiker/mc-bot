# Minecraft Discord Bot - Windows Installation Script
# This script handles WSL setup and hand-off to the Linux installer.

$ErrorActionPreference = "Stop"

# Color functions
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

Write-Info "`n[1/4] Checking WSL2 environment..."

# Check if WSL is installed
try {
    $wslStatus = wsl --status 2>$null
    if ($null -eq $wslStatus) { throw "WSL not found" }
    Write-Success "[OK] WSL2 is available."
} catch {
    Write-Warning "[WARN] WSL2 is not installed or enabled."
    Write-Info "Installing WSL2 components (requires reboot)..."
    wsl --install
    Write-Success "`n[SUCCESS] WSL2 installation triggered."
    Write-Warning "Your computer MUST be restarted to complete the setup."
    Write-Info "After rebooting, double-click install.bat again to continue."
    exit 0
}

Write-Info "`n[2/4] Ensuring Ubuntu distro is ready..."

# Check for Ubuntu distro
$ubuntu = wsl --list --quiet | Select-String "Ubuntu"
if ($null -eq $ubuntu) {
    Write-Info "Ubuntu not found. Installing Ubuntu distro..."
    wsl --install -d Ubuntu
    Write-Success "[OK] Ubuntu installation triggered."
} else {
    Write-Success "[OK] Ubuntu distro found."
}

Write-Info "`n[3/4] Preparing project directory (C:\MC-bot)..."

$destPath = "C:\MC-bot"
if (-not (Test-Path $destPath)) {
    Write-Info "Creating directory $destPath..."
    New-Item -ItemType Directory -Path $destPath | Out-Null
}

# Convert Windows path to WSL path
$wslPath = wsl wslpath "C:/MC-bot"

Write-Info "`n[4/4] Launching Linux installer inside WSL..."
Write-Warning "Note: If this is the first time running WSL, you may need to follow the prompt"
Write-Warning "inside the terminal to create a Linux username and password."
Write-Info "---------------------------------------------------------"

# Clone/Update and Run Installer
$gitCmd = "if [ ! -d .git ]; then git clone https://github.com/slogiker/mc-bot.git .; else git pull; fi"
$installCmd = "chmod +x install/install.sh && ./install/install.sh"

wsl -d Ubuntu -u root bash -c "mkdir -p $wslPath && cd $wslPath && $gitCmd && $installCmd"

if ($LASTEXITCODE -eq 0) {
    Write-Success "`n========================================================="
    Write-Success "   WINDOWS SETUP COMPLETE"
    Write-Success "========================================================="
    Write-Info "Your bot is now running inside the WSL Ubuntu environment."
    Write-Info "You can manage it from Discord using the /setup command."
} else {
    Write-Error "`n[ERROR] The Linux installer failed inside WSL."
    Write-Info "Check the terminal output above for specific errors."
    exit 1
}
