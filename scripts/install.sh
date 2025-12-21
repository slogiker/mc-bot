#!/bin/bash

# ============================================================================
# Minecraft Discord Bot - Installation Script
# ============================================================================
# This script performs the complete installation and setup of the bot.
# It will create virtual environment, install dependencies, collect
# credentials, and prepare the bot for first run.
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

echo -e "${BOLD}${CYAN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║        Minecraft Discord Bot - Installation Wizard            ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${YELLOW}This script will install and configure your Minecraft Discord bot.${NC}"
echo -e "${YELLOW}Make sure you have your Discord Bot Token ready!${NC}"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."
echo ""

# ============================================================================
# Step 1: Working Directory Detection
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 1/6] Working Directory Detection${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"
WORKING_DIR=$(pwd)
echo -e "Current directory: ${GREEN}${WORKING_DIR}${NC}"
echo ""
sleep 1

# ============================================================================
# Step 2: Python Virtual Environment Setup
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 2/6] Python Virtual Environment Setup${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

# Check if venv exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment found at: ${WORKING_DIR}/venv"
    VENV_PATH="${WORKING_DIR}/venv"
    echo -e "Using existing virtual environment"
else
    echo -e "${YELLOW}⚠${NC}  Creating virtual environment..."
    VENV_PATH="${WORKING_DIR}/venv"
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created at: ${VENV_PATH}"
fi

# Activate venv
echo -e "Activating virtual environment..."
source "${VENV_PATH}/bin/activate"

# Upgrade pip
echo -e "Upgrading pip..."
pip install --upgrade pip -q

# Install dependencies
echo -e "Installing dependencies from requirements.txt..."
pip install -r requirements.txt
echo -e "${GREEN}✓${NC} All dependencies installed successfully!"
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
    if [ "$MAJOR_VERSION" -ge 17 ] 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Java version is compatible (17+)"
    else
        echo -e "${YELLOW}⚠${NC}  Java version might be outdated (recommended: 17+)"
        echo -e "${YELLOW}⚠${NC}  Consider upgrading for best compatibility"
    fi
else
    echo -e "${RED}✗${NC} Java is not installed"
    echo -e "${YELLOW}Please install Java 17+ manually:${NC}"
    echo -e "  For Ubuntu/Debian: ${CYAN}sudo apt install openjdk-17-jdk${NC}"
    echo -e "  For Fedora: ${CYAN}sudo dnf install java-17-openjdk${NC}"
    echo -e "  Or use SDKMAN: ${CYAN}curl -s \"https://get.sdkman.io\" | bash${NC}"
    JAVA_PATH="java"
    echo ""
    read -p "Press Enter to continue anyway (you'll need to install Java later)..."
fi

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
while [ -z "$BOT_TOKEN" ]; do
    echo -e "${RED}✗${NC} Bot token cannot be empty"
    read -p "$(echo -e ${CYAN}Enter Discord Bot Token: ${NC})" BOT_TOKEN
done
echo -e "${GREEN}✓${NC} Bot token received (${#BOT_TOKEN} characters)"
echo ""

# RCON Password
read -p "$(echo -e ${CYAN}Enter RCON Password ${NC}[leave empty to generate]: )" RCON_PASSWORD
if [ -z "$RCON_PASSWORD" ]; then
    # Check if openssl is available
    if command -v openssl &> /dev/null; then
        RCON_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    else
        # Fallback to /dev/urandom
        RCON_PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 25 | head -n 1)
    fi
    echo -e "${GREEN}✓${NC} Generated RCON password: ${MAGENTA}${RCON_PASSWORD}${NC}"
    echo -e "${YELLOW}⚠${NC}  Save this password! You'll need it to configure your Minecraft server."
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
    # Expand to absolute path if relative
    if [[ "$MC_SERVER_DIR" != /* ]]; then
        MC_SERVER_DIR="${WORKING_DIR}/${MC_SERVER_DIR}"
    fi
    echo -e "${GREEN}✓${NC} Using: ${MC_SERVER_DIR}"
fi
echo ""

# Create .env file
echo -e "Creating ${GREEN}.env${NC} file..."
cat > .env << EOF
BOT_TOKEN="${BOT_TOKEN}"
RCON_PASSWORD="${RCON_PASSWORD}"
EOF
chmod 600 .env  # Secure the .env file
echo -e "${GREEN}✓${NC} .env file created and secured (permissions: 600)"
echo ""

# Update config.json
echo -e "Updating ${GREEN}config.json${NC}..."
# Use Python to safely update JSON
python3 << PYTHON_SCRIPT
import json

# Read existing config
with open('config.json', 'r') as f:
    config = json.load(f)

# Update values
config['rcon_host'] = '${SERVER_IP}'
config['server_directory'] = '${MC_SERVER_DIR}'
config['java_path'] = '${JAVA_PATH}'

# Write back
with open('config.json', 'w') as f:
    json.dump(config, f, indent='\t')
    f.write('\n')

print("✓ config.json updated successfully")
PYTHON_SCRIPT

echo -e "${GREEN}✓${NC} config.json updated with installation paths"
echo ""
sleep 1

# ============================================================================
# Step 5: Directory Setup
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 5/6] Directory Setup${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

# Create Minecraft server directory if it doesn't exist
if [ ! -d "$MC_SERVER_DIR" ]; then
    echo -e "Creating Minecraft server directory..."
    mkdir -p "$MC_SERVER_DIR"
    echo -e "${GREEN}✓${NC} Created: ${MC_SERVER_DIR}"
else
    echo -e "${GREEN}✓${NC} Directory already exists: ${MC_SERVER_DIR}"
fi

# Verify directory is writable
if [ -w "$MC_SERVER_DIR" ]; then
    echo -e "${GREEN}✓${NC} Directory is writable"
else
    echo -e "${RED}✗${NC} Warning: Directory is not writable"
fi

echo ""
sleep 1

# ============================================================================
# Step 6: Installation Summary
# ============================================================================
echo -e "${BOLD}${BLUE}[STEP 6/6] Installation Summary${NC}"
echo -e "${CYAN}───────────────────────────────────────────────────────${NC}"

echo -e "${BOLD}${GREEN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║              Installation Completed Successfully! ✓           ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

echo -e "${BOLD}Installation Summary:${NC}"
echo ""
echo -e "${GREEN}•${NC} Working directory: ${CYAN}${WORKING_DIR}${NC}"
echo -e "${GREEN}•${NC} Virtual environment: ${CYAN}${VENV_PATH}${NC}"
echo -e "${GREEN}•${NC} Java path: ${CYAN}${JAVA_PATH}${NC}"
echo -e "${GREEN}•${NC} Server IP: ${CYAN}${SERVER_IP}${NC}"
echo -e "${GREEN}•${NC} MC Server directory: ${CYAN}${MC_SERVER_DIR}${NC}"
echo -e "${GREEN}•${NC} RCON password: ${CYAN}${RCON_PASSWORD}${NC}"
echo ""

echo -e "${BOLD}Files Created/Modified:${NC}"
echo ""
echo -e "${GREEN}•${NC} ${CYAN}.env${NC} - Contains bot token and RCON password"
echo -e "${GREEN}•${NC} ${CYAN}config.json${NC} - Updated with installation paths"
echo -e "${GREEN}•${NC} ${CYAN}venv/${NC} - Python virtual environment with all dependencies"
echo -e "${GREEN}•${NC} ${CYAN}${MC_SERVER_DIR}/${NC} - Minecraft server directory"
echo ""

echo -e "${BOLD}${CYAN}Next Steps:${NC}"
echo ""
echo -e "1. ${BOLD}Start the bot:${NC}"
echo -e "   ${CYAN}source venv/bin/activate${NC}"
echo -e "   ${CYAN}python bot.py${NC}"
echo -e "   or in test mode: ${CYAN}python bot.py --test${NC}"
echo ""
echo -e "2. ${BOLD}In Discord, run:${NC} ${GREEN}/setup${NC}"
echo -e "   This will create the Discord channels and configure the bot"
echo ""
echo -e "3. ${BOLD}Install Minecraft Server:${NC}"
echo -e "   Follow the interactive prompts in Discord to install your server"
echo ""
echo -e "4. ${BOLD}Configure server.properties:${NC}"
echo -e "   Make sure to set these values in ${CYAN}${MC_SERVER_DIR}/server.properties${NC}:"
echo -e "   ${MAGENTA}enable-rcon=true${NC}"
echo -e "   ${MAGENTA}rcon.port=25575${NC}"
echo -e "   ${MAGENTA}rcon.password=${RCON_PASSWORD}${NC}"
echo ""

echo -e "${BOLD}${YELLOW}Important Notes:${NC}"
echo ""
echo -e "• Your credentials are stored in ${GREEN}.env${NC} (not tracked by git)"
echo -e "• The RCON password must match in both bot config and server.properties"
echo -e "• For multiplayer, you'll need to configure port forwarding or use playit.gg"
echo -e "• Run ${GREEN}./install-dry-run.sh${NC} anytime to preview configuration changes"
echo ""

echo -e "${GREEN}Happy Minecrafting! 🎮⛏️${NC}"
echo ""
