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
        curl -fsSL https://get-docker.com -o get-docker.sh
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
echo -e "${BLUE}[INFO] Starting Docker containers using $DOCKER_COMPOSE_CMD... (Building fresh image)${NC}"
$DOCKER_COMPOSE_CMD up -d --build

# Wait a moment for container to initialize
echo -e "${BLUE}[INFO] Waiting for container to initialize...${NC}"
sleep 5

# Check if container is actually running
if ! $DOCKER_COMPOSE_CMD ps | grep -q "Up"; then
    echo -e "${RED}[ERROR] Container failed to start!${NC}"
    echo -e "${YELLOW}[WARN] checking logs:${NC}"
    $DOCKER_COMPOSE_CMD logs
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                ║${NC}"
echo -e "${GREEN}║           Installation Completed Successfully! ✓              ║${NC}"
echo -e "${GREEN}║                                                                ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get current working directory and RCON password for display
WORKING_DIR=$(pwd)
if [ -f .env ]; then
    RCON_PASSWORD=$(grep "RCON_PASSWORD" .env | cut -d '=' -f2 | tr -d '"' | tr -d ' ')
fi

echo -e "${BLUE}Installation Summary:${NC}"
echo ""
echo -e "${GREEN}•${NC} Working directory: ${CYAN}${WORKING_DIR}${NC}"
echo -e "${GREEN}•${NC} Docker compose: ${CYAN}${DOCKER_COMPOSE_CMD}${NC}"
echo -e "${GREEN}•${NC} Container status: ${CYAN}Running${NC}"
echo -e "${GREEN}•${NC} RCON password: ${CYAN}${RCON_PASSWORD}${NC}"
echo ""

echo -e "${BLUE}Files Created/Modified:${NC}"
echo ""
echo -e "${GREEN}•${NC} ${CYAN}.env${NC} - Contains bot token and RCON password"
echo -e "${GREEN}•${NC} ${CYAN}mc-server/${NC} - Minecraft server directory (mounted)"
echo -e "${GREEN}•${NC} ${CYAN}backups/${NC} - Backup storage directory"
echo -e "${GREEN}•${NC} ${CYAN}logs/${NC} - Bot logs directory"
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo -e "1. ${CYAN}In Discord, run:${NC} ${GREEN}/setup${NC}"
echo -e "   This will create the Discord channels and configure the bot"
echo ""
echo -e "2. ${CYAN}Install Minecraft Server:${NC}"
echo -e "   Follow the interactive prompts in Discord to install your server"
echo ""
echo -e "3. ${CYAN}Configure server.properties:${NC}"
echo -e "   Make sure to set these values in ${CYAN}mc-server/server.properties${NC}:"
echo -e "   ${YELLOW}enable-rcon=true${NC}"
echo -e "   ${YELLOW}rcon.port=25575${NC}"
echo -e "   ${YELLOW}rcon.password=${RCON_PASSWORD}${NC}"
echo ""

echo -e "${BLUE}Useful Commands:${NC}"
echo ""
echo -e "   View logs:        ${CYAN}$DOCKER_COMPOSE_CMD logs -f mc-bot${NC}"
echo -e "   Stop bot:         ${CYAN}$DOCKER_COMPOSE_CMD down${NC}"
echo -e "   Restart bot:      ${CYAN}$DOCKER_COMPOSE_CMD restart${NC}"
echo -e "   Access shell:     ${CYAN}$DOCKER_COMPOSE_CMD exec mc-bot bash${NC}"
echo -e "   Rebuild:          ${CYAN}$DOCKER_COMPOSE_CMD up -d --build${NC}"
echo ""

echo -e "${YELLOW}Important Notes:${NC}"
echo ""
echo -e "• Your credentials are stored in ${GREEN}.env${NC} (not tracked by git)"
echo -e "• The RCON password must match in both bot config and server.properties"
echo -e "• For multiplayer, you'll need to configure port forwarding or use playit.gg"
echo ""

echo -e "${GREEN}Happy Minecrafting! 🎮⛏️${NC}"
echo ""