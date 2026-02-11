#Requires -Version 5.1

# Minecraft Discord Bot - Windows Installation Script
# PowerShell script to set up and start the bot in Docker on Windows

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Blue { Write-Host $args -ForegroundColor Blue }

# Header
Write-Info "----------------------------------------"
Write-Info "   Minecraft Discord Bot - Docker Setup"
Write-Info "----------------------------------------"
Write-Host ""

# Function to generate random password
function New-RandomPassword {
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    $password = ""
    for ($i = 0; $i -lt 24; $i++) {
        $password += $chars[(Get-Random -Maximum $chars.Length)]
    }
    return $password
}

# Check if .env exists and is configured
if (-not (Test-Path ".env")) {
    Write-Warning "[WARN] .env file not found! Starting setup..."
    Write-Host ""
    
    # Prompt for Discord Bot Token
    Write-Blue "[INFO] Please enter your Discord Bot Token:"
    Write-Host "       (Get it from: https://discord.com/developers/applications)"
    $bot_token = Read-Host "       > BOT_TOKEN"
    
    # Validate token is not empty
    if ([string]::IsNullOrWhiteSpace($bot_token)) {
        Write-Error "[ERROR] Bot token cannot be empty!"
        exit 1
    }
    
    # Generate random RCON password
    $rcon_password = New-RandomPassword
    
    Write-Host ""
    Write-Success "[OK] Auto-generated RCON password: $rcon_password"
    Write-Host ""
    
    # Create .env file
    $envContent = @"
# Discord Bot Configuration
BOT_TOKEN=$bot_token

# Minecraft RCON Password (auto-generated)
RCON_PASSWORD=$rcon_password
"@
    $envContent | Out-File -FilePath ".env" -Encoding utf8 -NoNewline
    
    Write-Success "[OK] Created .env file with your configuration!"
    Write-Host ""
} else {
    # Check if .env is complete
    $envContent = Get-Content ".env" -Raw
    $hasBotToken = $envContent -match "BOT_TOKEN=.+"
    $hasRconPassword = $envContent -match "RCON_PASSWORD=.+"
    
    if (-not $hasBotToken -or -not $hasRconPassword) {
        Write-Warning "[WARN] .env file exists but appears incomplete!"
        Write-Blue "[INFO] Please ensure .env contains:"
        Write-Host "       - BOT_TOKEN=your_discord_bot_token"
        Write-Host "       - RCON_PASSWORD=your_rcon_password"
        Write-Host ""
        $reconfigure = Read-Host "       > Do you want to reconfigure .env? (y/N)"
        
        if ($reconfigure -match "^[Yy]$") {
            # Backup existing .env
            $backupDir = ".backups"
            if (-not (Test-Path $backupDir)) {
                New-Item -ItemType Directory -Path $backupDir | Out-Null
            }
            $timestamp = [DateTimeOffset]::Now.ToUnixTimeSeconds()
            Copy-Item ".env" "$backupDir/.env.backup.$timestamp"
            Write-Info "[INFO] Backed up existing .env to .backups/"
            
            # Prompt for Discord Bot Token
            Write-Host ""
            Write-Blue "[INFO] Please enter your Discord Bot Token:"
            $bot_token = Read-Host "       > BOT_TOKEN"
            
            if ([string]::IsNullOrWhiteSpace($bot_token)) {
                Write-Error "[ERROR] Bot token cannot be empty!"
                exit 1
            }
            
            # Generate random RCON password
            $rcon_password = New-RandomPassword
            
            Write-Host ""
            Write-Success "[OK] Auto-generated RCON password: $rcon_password"
            Write-Host ""
            
            # Create .env file
            $envContent = @"
# Discord Bot Configuration
BOT_TOKEN=$bot_token

# Minecraft RCON Password (auto-generated)
RCON_PASSWORD=$rcon_password
"@
            $envContent | Out-File -FilePath ".env" -Encoding utf8 -NoNewline
            
            Write-Success "[OK] Updated .env file!"
            Write-Host ""
        } else {
            Write-Warning "[WARN] Please configure .env manually and run this script again."
            exit 1
        }
    }
}

# Create necessary directories
Write-Blue "[INFO] Creating directories..."
$directories = @("mc-server", "backups", "logs")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

# Check if Docker is installed
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Warning "[WARN] Docker is not installed."
    Write-Blue "[INFO] Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    Write-Host "       Docker is required to run this bot."
    Write-Host "       After installing Docker Desktop, please restart this script."
    exit 1
}

# Check if Docker daemon is running
Write-Blue "[INFO] Checking if Docker daemon is running..."
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon not accessible"
    }
} catch {
    Write-Warning "[WARN] Docker daemon is not running or not accessible."
    Write-Host ""
    Write-Blue "[INFO] Please ensure Docker Desktop is:"
    Write-Host "       1. Installed (download from: https://www.docker.com/products/docker-desktop)"
    Write-Host "       2. Started (look for Docker Desktop icon in system tray)"
    Write-Host "       3. Fully initialized (wait for 'Docker Desktop is running' notification)"
    Write-Host ""
    Write-Host "       After Docker Desktop is running, please run this script again."
    exit 1
}

# Additional check: Try to ping Docker
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not responding"
    }
} catch {
    Write-Warning "[WARN] Docker is installed but not responding."
    Write-Blue "[INFO] Please check:"
    Write-Host "       - Docker Desktop is running (check system tray)"
    Write-Host "       - Docker Desktop has finished starting (may take 30-60 seconds)"
    Write-Host "       - No firewall is blocking Docker"
    Write-Host ""
    Write-Host "       Then run this script again."
    exit 1
}

Write-Success "[OK] Docker daemon is running"

# Determine if we should use "docker-compose" or "docker compose"
$dockerComposeCmd = $null
$dockerComposeCmdName = $null

$dockerComposeCmdCheck = Get-Command docker-compose -ErrorAction SilentlyContinue
if ($dockerComposeCmdCheck) {
    $dockerComposeCmd = "docker-compose"
    $dockerComposeCmdName = "docker-compose"
} else {
    # Try docker compose (newer syntax)
    try {
        docker compose version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerComposeCmd = "docker compose"
            $dockerComposeCmdName = "docker compose"
        }
    } catch {
        # docker compose not available
    }
}

if (-not $dockerComposeCmd) {
    Write-Error "[ERROR] Docker Compose is not installed or not in PATH."
    Write-Host "       Please install Docker Compose or ensure 'docker compose' works."
    exit 1
}

# Start with docker-compose
Write-Host ""
Write-Blue "[INFO] Starting Docker containers using $dockerComposeCmdName... (Building fresh image)"

# Execute the appropriate docker compose command
$dockerOutput = $null
if ($dockerComposeCmd -eq "docker-compose") {
    $dockerOutput = & docker-compose up -d --build 2>&1
} else {
    $dockerOutput = & docker compose up -d --build 2>&1
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "[ERROR] Failed to start Docker containers!"
    Write-Host ""
    
    # Check for specific Docker Desktop errors
    $errorText = $dockerOutput -join "`n"
    if ($errorText -match "dockerDesktopLinuxEngine|The system cannot find the file specified|daemon.*not running") {
        Write-Warning "[WARN] Docker Desktop appears to not be running or not fully started."
        Write-Host ""
        Write-Blue "[INFO] Please:"
        Write-Host "       1. Open Docker Desktop (look for icon in system tray or Start menu)"
        Write-Host "       2. Wait for Docker Desktop to fully start (may take 30-60 seconds)"
        Write-Host "       3. Look for 'Docker Desktop is running' notification"
        Write-Host "       4. Check system tray - Docker icon should be steady (not animating)"
        Write-Host ""
        Write-Host "       Then run this script again."
    } else {
        Write-Host "Error details:"
        Write-Host $errorText
    }
    exit 1
}

# Wait a moment for container to initialize
Write-Blue "[INFO] Waiting for container to initialize..."
Start-Sleep -Seconds 5

# Check if container is actually running
if ($dockerComposeCmd -eq "docker-compose") {
    $containerStatus = & docker-compose ps 2>$null
} else {
    $containerStatus = & docker compose ps 2>$null
}

if ($containerStatus -notmatch "Up") {
    Write-Error "[ERROR] Container failed to start!"
    Write-Warning "[WARN] checking logs:"
    if ($dockerComposeCmd -eq "docker-compose") {
        & docker-compose logs
    } else {
        & docker compose logs
    }
    exit 1
}

Write-Host ""
Write-Success "[SUCCESS] Bot started successfully!"
Write-Host ""
Write-Info "Useful commands:"
Write-Host "   View logs:        $dockerComposeCmdName logs -f mc-bot"
Write-Host "   Stop bot:         $dockerComposeCmdName down"
Write-Host "   Restart bot:      $dockerComposeCmdName restart"
Write-Host "   Access shell:     $dockerComposeCmdName exec mc-bot bash"
Write-Host "   Rebuild:          $dockerComposeCmdName up -d --build"
Write-Host ""
