#!/bin/bash

# Minecraft Discord Bot - Docker Startup Script
# Simple script to start the bot in Docker

set -e

# ANSI Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}----------------------------------------${NC}"
echo -e "${CYAN}   Minecraft Discord Bot - Docker Setup ${NC}"
echo -e "${CYAN}----------------------------------------${NC}"
echo ""

# Check if .env exists and is configured
if [ ! -f .env ]; then
    echo -e "${YELLOW}[WARN] .env file not found! Starting setup...${NC}"
    echo ""
    
    # Prompt for Discord Bot Token
    echo -e "${BLUE}[INFO] Please enter your Discord Bot Token:${NC}"
    echo "       (Get it from: https://discord.com/developers/applications)"
    read -p "       > BOT_TOKEN: " bot_token
    
    # Validate token is not empty
    if [ -z "$bot_token" ]; then
        echo -e "${RED}[ERROR] Bot token cannot be empty!${NC}"
        exit 1
    fi
    
    # Generate random RCON password
    rcon_password=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
    
    echo ""
    echo -e "${GREEN}[OK] Auto-generated RCON password: ${NC}$rcon_password"
    echo ""
    
    # Create .env file
    cat > .env << EOF
# Discord Bot Configuration
BOT_TOKEN=$bot_token

# Minecraft RCON Password (auto-generated)
RCON_PASSWORD=$rcon_password
EOF
    
    echo -e "${GREEN}[OK] Created .env file with your configuration!${NC}"
    echo ""
elif ! grep -q "BOT_TOKEN=." .env 2>/dev/null || ! grep -q "RCON_PASSWORD=." .env 2>/dev/null; then
    echo -e "${YELLOW}[WARN] .env file exists but appears incomplete!${NC}"
    echo -e "${BLUE}[INFO] Please ensure .env contains:${NC}"
    echo "       - BOT_TOKEN=your_discord_bot_token"
    echo "       - RCON_PASSWORD=your_rcon_password"
    echo ""
    read -p "       > Do you want to reconfigure .env? (y/N): " reconfigure
    
    if [[ $reconfigure =~ ^[Yy]$ ]]; then
        # Backup existing .env
        mkdir -p .backups
        cp .env .backups/.env.backup.$(date +%s)
        echo -e "${CYAN}[INFO] Backed up existing .env to .backups/${NC}"
        
        # Prompt for Discord Bot Token
        echo ""
        echo -e "${BLUE}[INFO] Please enter your Discord Bot Token:${NC}"
        read -p "       > BOT_TOKEN: " bot_token
        
        if [ -z "$bot_token" ]; then
            echo -e "${RED}[ERROR] Bot token cannot be empty!${NC}"
            exit 1
        fi
        
        # Generate random RCON password
        rcon_password=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
        
        echo ""
        echo -e "${GREEN}[OK] Auto-generated RCON password: ${NC}$rcon_password"
        echo ""
        
        # Create .env file
        cat > .env << EOF
# Discord Bot Configuration
BOT_TOKEN=$bot_token

# Minecraft RCON Password (auto-generated)
RCON_PASSWORD=$rcon_password
EOF
        
        echo -e "${GREEN}[OK] Updated .env file!${NC}"
        echo ""
    else
        echo -e "${YELLOW}[WARN] Please configure .env manually and run this script again.${NC}"
        exit 1
    fi
fi

# Create necessary directories
echo -e "${BLUE}[INFO] Creating directories...${NC}"
mkdir -p mc-server backups logs

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}[WARN] Docker is not installed.${NC}"
    echo -e "${BLUE}[INFO] Would you like to install Docker automatically? (y/N)${NC}"
    read -p "       > " install_docker
    
    if [[ $install_docker =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}[INFO] Installing Docker... (This may require your password)${NC}"
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        rm get-docker.sh
        
        echo -e "${BLUE}[INFO] Adding current user to 'docker' group...${NC}"
        sudo usermod -aG docker $USER
        
        echo -e "${GREEN}[SUCCESS] Docker installed successfully!${NC}"
        echo -e "${YELLOW}[WARN] You may need to log out and back in for group changes to take effect.${NC}"
        echo -e "${YELLOW}[WARN] If you get a permission error below, try restarting your session.${NC}"
    else
        echo -e "${RED}[ERROR] Docker is required to run this bot.${NC}"
        echo "       Please install Docker manually and try again."
        exit 1
    fi
fi

# Determine if we should use "docker-compose" or "docker compose"
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}[ERROR] Docker Compose is not installed or not in PATH.${NC}"
    echo "       Please install it or ensure 'docker compose' works."
    exit 1
fi

# Start with docker-compose
echo ""
echo -e "${BLUE}[INFO] Starting Docker containers using $DOCKER_COMPOSE_CMD...${NC}"
$DOCKER_COMPOSE_CMD up -d

echo ""
echo -e "${GREEN}[SUCCESS] Bot started successfully!${NC}"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo "   View logs:        $DOCKER_COMPOSE_CMD logs -f mc-bot"
echo "   Stop bot:         $DOCKER_COMPOSE_CMD down"
echo "   Restart bot:      $DOCKER_COMPOSE_CMD restart"
echo "   Access shell:     $DOCKER_COMPOSE_CMD exec mc-bot bash"
echo "   Rebuild:          $DOCKER_COMPOSE_CMD up -d --build"
echo ""
