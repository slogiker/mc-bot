#!/bin/bash
set -e

# Minecraft Discord Bot - Linux/WSL Setup Script
# This script is intended to run INSIDE WSL (Ubuntu).

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}----------------------------------------${NC}"
echo -e "${CYAN}   Minecraft Discord Bot - WSL Setup    ${NC}"
echo -e "${CYAN}----------------------------------------${NC}"
echo ""

# Ensure we are root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Please run as root (or via install.bat info).${NC}"
  exit 1
fi

echo -e "${BLUE}[INFO] Updating package lists...${NC}"
apt-get update

# 1. Install Docker Engine (Native)
if ! command -v docker &> /dev/null; then
    echo -e "${BLUE}[INFO] Docker not found. Installing Docker Engine...${NC}"
    
    # Remove conflicting packages
    for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do 
        apt-get remove -y $pkg || true
    done

    # Add Docker's official GPG key
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add the repository to Apt sources
    echo \
      "deb [arch=\"$(dpkg --print-architecture)\" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null
      
    apt-get update
    
    # Install Docker packages
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    echo -e "${GREEN}[SUCCESS] Docker Engine installed.${NC}"
else
    echo -e "${GREEN}[OK] Docker is already installed.${NC}"
fi

# Ensure Docker service is running (WSL sometimes needs manual start)
if ! service docker status > /dev/null; then
    echo -e "${YELLOW}[WARN] Docker service not running. Starting...${NC}"
    service docker start
fi

# 2. Check/Install Python and Java
echo -e "${BLUE}[INFO] Checking dependencies...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}[WARN] Python3 not found. Installing...${NC}"
    apt-get install -y python3 python3-pip
else
    echo -e "${GREEN}[OK] Python3 is installed.${NC}"
fi

if ! command -v java &> /dev/null; then
    echo -e "${YELLOW}[WARN] Java not found. Installing OpenJDK 17...${NC}"
    apt-get install -y openjdk-17-jre-headless
else
    echo -e "${GREEN}[OK] Java is installed.${NC}"
fi

# 3. Bot Setup (.env)
if [ ! -f .env ]; then
    echo -e "${YELLOW}[WARN] .env file not found! Starting setup...${NC}"
    
    echo -e "${BLUE}[INFO] Please enter your Discord Bot Token:${NC}"
    read -p "       > BOT_TOKEN: " bot_token
    
    if [ -z "$bot_token" ]; then
        echo -e "${RED}[ERROR] Bot token cannot be empty!${NC}"
        exit 1
    fi
    
    rcon_password=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
    
    cat > .env << EOF
# Discord Bot Configuration
BOT_TOKEN=$bot_token

# Minecraft RCON Password (auto-generated)
RCON_PASSWORD=$rcon_password
EOF
    echo -e "${GREEN}[OK] Created .env file.${NC}"
fi

# 4. Start Bot
echo -e "${BLUE}[INFO] Starting Bot via Docker Compose...${NC}"

# Use 'docker compose' plugin
mkdir -p mc-server backups logs

docker compose up -d --build

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}[SUCCESS] Bot started successfully!${NC}"
    echo -e "${CYAN}Logs: docker compose logs -f mc-bot${NC}"
else
    echo -e "${RED}[ERROR] Failed to start bot.${NC}"
    exit 1
fi
