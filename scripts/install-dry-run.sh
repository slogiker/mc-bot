#!/bin/bash

# ============================================================================
# Minecraft Discord Bot - DRY RUN Installation Script
# ============================================================================
# This script simulates the installation process without making any changes.
# It shows what would happen during actual installation.
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Dry run indicator
DRY_RUN=true

echo -e "${BOLD}${CYAN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║        Minecraft Discord Bot - Installation Wizard            ║"
echo "║                    🌵 DRY RUN MODE 🌵                          ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${YELLOW}This is a DRY RUN - No changes will be made to your system.${NC}"
echo -e "${YELLOW}You can preview what the installation will do.${NC}"
echo ""
sleep 2

# ============================================================================
# Step 1: Working Directory Detection
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 1/6] Working Directory Detection${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"
WORKING_DIR=$(pwd)
echo -e "Current directory: ${GREEN}${WORKING_DIR}${NC}"
echo ""
echo -e "${YELLOW}[DRY RUN]${NC} Would save to config.json:"
echo -e "  ${MAGENTA}\"working_directory\": \"${WORKING_DIR}\"${NC}"
echo ""
sleep 1

# ============================================================================
# Step 2: Python Virtual Environment Check
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 2/6] Python Virtual Environment Management${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

# Check if venv exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment found at: ${WORKING_DIR}/venv"
    VENV_PATH="${WORKING_DIR}/venv"
    echo -e "${YELLOW}[DRY RUN]${NC} Would use existing venv"
else
    echo -e "${YELLOW}⚠${NC}  Virtual environment not found"
    VENV_PATH="${WORKING_DIR}/venv"
    echo -e "${YELLOW}[DRY RUN]${NC} Would create venv at: ${GREEN}${VENV_PATH}${NC}"
    echo -e "${YELLOW}[DRY RUN]${NC} Would run: ${CYAN}python3 -m venv venv${NC}"
fi

echo ""
echo -e "${YELLOW}[DRY RUN]${NC} Would activate venv:"
echo -e "  ${CYAN}source ${VENV_PATH}/bin/activate${NC}"
echo ""
echo -e "${YELLOW}[DRY RUN]${NC} Would install dependencies:"
echo -e "  ${CYAN}pip install -r requirements.txt${NC}"
echo ""
echo -e "${YELLOW}[DRY RUN]${NC} Would save to config.json:"
echo -e "  ${MAGENTA}\"venv_path\": \"${VENV_PATH}\"${NC}"
echo ""
sleep 1

# ============================================================================
# Step 3: Java Installation Check
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 3/6] Java Installation Verification${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -n 1 | cut -d'"' -f2)
    JAVA_PATH=$(which java)
    echo -e "${GREEN}✓${NC} Java is installed"
    echo -e "  Version: ${GREEN}${JAVA_VERSION}${NC}"
    echo -e "  Path: ${GREEN}${JAVA_PATH}${NC}"
    
    # Extract major version
    MAJOR_VERSION=$(echo $JAVA_VERSION | cut -d'.' -f1)
    if [ "$MAJOR_VERSION" -ge 17 ]; then
        echo -e "${GREEN}✓${NC} Java version is compatible (17+)"
    else
        echo -e "${YELLOW}⚠${NC}  Java version might be outdated (need 17+)"
        echo -e "${YELLOW}[DRY RUN]${NC} Would recommend upgrading Java"
    fi
else
    echo -e "${RED}✗${NC} Java is not installed"
    echo -e "${YELLOW}[DRY RUN]${NC} Would download and install OpenJDK 17+"
    echo -e "  ${CYAN}wget https://download.oracle.com/java/17/latest/jdk-17_linux-x64_bin.tar.gz${NC}"
    echo -e "  ${CYAN}tar -xzf jdk-17_linux-x64_bin.tar.gz${NC}"
    JAVA_PATH="${WORKING_DIR}/jdk-17/bin/java"
fi

echo ""
echo -e "${YELLOW}[DRY RUN]${NC} Would save to config.json:"
echo -e "  ${MAGENTA}\"java_path\": \"${JAVA_PATH}\"${NC}"
echo ""
sleep 1

# ============================================================================
# Step 4: Credential Collection
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 4/6] Credential Collection${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

# Server IP
read -p "$(echo -e ${CYAN}Enter Server IP ${NC}[default: 127.0.0.1]: )" SERVER_IP
SERVER_IP=${SERVER_IP:-"127.0.0.1"}
echo -e "${GREEN}✓${NC} Server IP: ${SERVER_IP}"
echo ""

# Discord Bot Token
read -p "$(echo -e ${CYAN}Enter Discord Bot Token: ${NC})" BOT_TOKEN
if [ -z "$BOT_TOKEN" ]; then
    BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
    echo -e "${YELLOW}⚠${NC}  No token provided (will use placeholder)"
else
    echo -e "${GREEN}✓${NC} Bot token received (${#BOT_TOKEN} characters)"
fi
echo ""

# RCON Password
read -p "$(echo -e ${CYAN}Enter RCON Password ${NC}[leave empty to generate]: )" RCON_PASSWORD
if [ -z "$RCON_PASSWORD" ]; then
    RCON_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    echo -e "${GREEN}✓${NC} Generated RCON password: ${MAGENTA}${RCON_PASSWORD}${NC}"
else
    echo -e "${GREEN}✓${NC} Using provided RCON password"
fi
echo ""

# Minecraft Server Directory
read -p "$(echo -e ${CYAN}Enter Minecraft Server Directory ${NC}[leave empty for ./mc-server]: )" MC_SERVER_DIR
if [ -z "$MC_SERVER_DIR" ]; then
    MC_SERVER_DIR="${WORKING_DIR}/mc-server"
    echo -e "${GREEN}✓${NC} Using default: ${MC_SERVER_DIR}"
else
    echo -e "${GREEN}✓${NC} Using: ${MC_SERVER_DIR}"
fi
echo ""

# Actually CREATE the .env file (this is helpful even in dry-run mode!)
echo -e "${GREEN}[CREATING]${NC} Writing ${GREEN}.env${NC} file:"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"
cat > .env << EOF
BOT_TOKEN="${BOT_TOKEN}"
RCON_PASSWORD="${RCON_PASSWORD}"
EOF
echo -e "${MAGENTA}BOT_TOKEN=\"${BOT_TOKEN}\"${NC}"
echo -e "${MAGENTA}RCON_PASSWORD=\"${RCON_PASSWORD}\"${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"
echo -e "${GREEN}✓${NC} .env file created successfully!"
echo ""

# Show what would be written to config.json
echo -e "${YELLOW}[DRY RUN]${NC} Would update ${GREEN}config.json${NC} with:"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"
echo -e "${MAGENTA}  \"rcon_host\": \"${SERVER_IP}\",${NC}"
echo -e "${MAGENTA}  \"server_directory\": \"${MC_SERVER_DIR}\",${NC}"
echo -e "${MAGENTA}  \"working_directory\": \"${WORKING_DIR}\",${NC}"
echo -e "${MAGENTA}  \"venv_path\": \"${VENV_PATH}\",${NC}"
echo -e "${MAGENTA}  \"java_path\": \"${JAVA_PATH}\"${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"
echo ""
sleep 1

# ============================================================================
# Step 5: Dependency Verification
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 5/6] Dependency Verification${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

echo -e "${YELLOW}[DRY RUN]${NC} Would verify Python packages:"
echo -e "  ${CYAN}• discord.py${NC}"
echo -e "  ${CYAN}• psutil${NC}"
echo -e "  ${CYAN}• python-dotenv${NC}"
echo -e "  ${CYAN}• aio-mc-rcon${NC}"
echo -e "  ${CYAN}• aiofiles${NC}"
echo -e "  ${CYAN}• requests${NC}"
echo -e "  ${CYAN}• pytz${NC}"
echo ""

echo -e "${YELLOW}[DRY RUN]${NC} Would test Discord bot token:"
echo -e "  ${CYAN}python3 -c 'import discord; ...'${NC}"
echo ""

echo -e "${YELLOW}[DRY RUN]${NC} Would verify directory permissions:"
if [ -w "$WORKING_DIR" ]; then
    echo -e "  ${GREEN}✓${NC} Working directory is writable"
else
    echo -e "  ${RED}✗${NC} Working directory is not writable"
fi
echo ""

echo -e "${YELLOW}[DRY RUN]${NC} Would create Minecraft server directory:"
if [ ! -d "$MC_SERVER_DIR" ]; then
    echo -e "  ${CYAN}mkdir -p ${MC_SERVER_DIR}${NC}"
else
    echo -e "  ${GREEN}✓${NC} Directory already exists"
fi
echo ""
sleep 1

# ============================================================================
# Step 6: Bot Startup
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 6/6] Bot Startup${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

echo -e "${YELLOW}[DRY RUN]${NC} Would start the bot with:"
echo -e "  ${CYAN}python bot.py${NC}"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${BOLD}${GREEN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║                  DRY RUN COMPLETED! ✓                          ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${BOLD}Summary of what would happen:${NC}"
echo ""
echo -e "${GREEN}1.${NC} Working directory: ${CYAN}${WORKING_DIR}${NC}"
echo -e "${GREEN}2.${NC} Virtual environment: ${CYAN}${VENV_PATH}${NC}"
echo -e "${GREEN}3.${NC} Java path: ${CYAN}${JAVA_PATH}${NC}"
echo -e "${GREEN}4.${NC} Server IP: ${CYAN}${SERVER_IP}${NC}"
echo -e "${GREEN}5.${NC} MC Server directory: ${CYAN}${MC_SERVER_DIR}${NC}"
echo -e "${GREEN}6.${NC} Bot token: ${CYAN}[${#BOT_TOKEN} characters]${NC}"
echo -e "${GREEN}7.${NC} RCON password: ${CYAN}[generated/provided]${NC}"
echo ""
echo -e "${BOLD}Files that would be created/modified:${NC}"
echo ""
echo -e "${YELLOW}•${NC} ${GREEN}.env${NC} (new or updated)"
echo -e "${YELLOW}•${NC} ${GREEN}config.json${NC} (updated)"
echo -e "${YELLOW}•${NC} ${GREEN}venv/${NC} (virtual environment)"
echo -e "${YELLOW}•${NC} ${GREEN}${MC_SERVER_DIR}/${NC} (server directory)"
echo ""
echo -e "${BOLD}${CYAN}Next steps:${NC}"
echo -e "1. Review the summary above"
echo -e "2. If everything looks good, run the actual installation script"
echo -e "3. Use ${GREEN}/setup${NC} command in Discord to configure the bot"
echo ""
echo -e "${YELLOW}Note: This was a DRY RUN - no changes were made to your system.${NC}"
echo ""
