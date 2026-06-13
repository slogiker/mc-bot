#!/bin/bash

# Minecraft Discord Bot - Linux/Docker Installer
# ---------------------------------------------------
# This script handles:
# 1. Dependency checks (Docker, Git, etc.)
# 2. Package manager support (apt, dnf, pacman, apk)
# 3. Environment configuration (.env)
# 4. Docker container deployment
# 5. Playit.gg tunnel setup (optional)

set -e

# Colors & Styles
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'

# Icons
ICON_CHECK="${GREEN}✔${NC}"
ICON_CROSS="${RED}✖${NC}"
ICON_INFO="${CYAN}ℹ${NC}"
ICON_WARN="${YELLOW}⚠${NC}"
ICON_ROCKET="🚀"
ICON_GEAR="⚙️"
ICON_KEY="🔑"
ICON_LINK="🔗"
ICON_BOX="📦"
ICON_DISK="💾"

# Error Handler
handle_error() {
    echo -e "\n${RED}${BOLD}${ICON_CROSS} Oops! Something went wrong during installation.${NC}"
    echo -e "${RED}Error occurred on line $1.${NC}"
    echo -e "Check the output above for clues. If you're stuck, feel free to open an issue on GitHub."
    exit 1
}
trap 'handle_error $LINENO' ERR

# Parse arguments
ORIG_ARGS="$@"
SKIP_START=0
for arg in "$@"; do
    case $arg in
        --skip-start)
        SKIP_START=1
        shift
        ;;
    esac
done

# Ensure we are in the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "$SCRIPT_DIR")" == "install" ]]; then
    cd "$(dirname "$SCRIPT_DIR")"
fi

# ---------------------------------------------------------
# 1. Welcome Header
# ---------------------------------------------------------
echo -e "${CYAN}${BOLD}"
echo -e "  ⚡ Minecraft Discord Bot - Linux Installer"
echo -e "  ──────────────────────────────────────────"
echo -e "  ${DIM}Version: 1.1.1 | Playit: v1.0.10${NC}\n"

# ---------------------------------------------------------
# 0. Initial Warnings & Permissions
# ---------------------------------------------------------

# Storage Warning
echo -e "  ${ICON_DISK} ${BOLD}Note on Storage:${NC}"
echo -e "  A full installation (Docker images + Minecraft server + Backups)"
echo -e "  can take up ${YELLOW}5GB or more${NC} of disk space."
echo -e "  Please ensure you have enough space before proceeding.\n"
echo -ne "  Do you wish to continue? [Y/n] "
read continue_install
if [[ -n "$continue_install" && ! $continue_install =~ ^[Yy]$ ]]; then
    echo -e "\n  Installation cancelled by user."
    exit 0
fi
echo ""

# Sudo / Permission Handling
SUDO=""
TARGET_USER=""
if [ "$EUID" -ne 0 ]; then
    if command -v sudo &> /dev/null; then
        SUDO="sudo"
        TARGET_USER=$USER
        echo -e "  ${ICON_CHECK} ${GREEN}'sudo' is available. Privileged operations will be requested when needed.${NC}"
    else
        echo -e "  ${ICON_CROSS} ${RED}'sudo' command not found, but is required for automated installation.${NC}"
        echo -e "  Please install 'sudo' and run this script as a user with sudo privileges."
        exit 1
    fi
else
    # If running as root, we need to find the original user to own files.
    if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
        TARGET_USER="$SUDO_USER"
        SUDO="sudo" # We are already root, but this makes commands consistent
        echo -e "  ${ICON_WARN} ${YELLOW}Running with 'sudo'. File ownership will be set for user '$TARGET_USER'.${NC}"
    else
        # This is a last resort, not a recommended path.
        echo -e "  ${ICON_CROSS} ${RED}Running as root directly is not supported.${NC}"
        echo -e "  Please run this script from a non-root user account using 'sudo' if needed, for example:"
        echo -e "  ${CYAN}sudo -u your-user-name ./install.sh${NC}"
        exit 1
    fi
fi


# Detect existing installation
if [ -f .env ] && command -v docker &> /dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^mc-bot$'; then
    echo -e "\n  ${ICON_INFO} ${YELLOW}An existing installation was detected.${NC}"
    echo -e "    ${DIM}Note: Your Minecraft server files, backups, and logs are stored in local folders${NC}"
    echo -e "    ${DIM}and will remain safe during reconfiguration.${NC}"
    echo ""
    echo -e "    ${CYAN}${BOLD}1)${NC} Reconfigure & Reinstall ${DIM}(fresh setup)${NC}"
    echo -e "    ${CYAN}${BOLD}2)${NC} Update code only ${DIM}(git pull + rebuild)${NC}"
    echo -e "    ${CYAN}${BOLD}3)${NC} Cancel"
    echo ""
    echo -ne "  Choose an option [1/2/3]: "
    read INSTALL_MODE
    case $INSTALL_MODE in
        1)
            echo -e "\n  ${BLUE}${ICON_GEAR} Stopping services for reconfiguration...${NC}"
            docker stop mc-bot &>/dev/null || true
            
            if [ -f "data/playit_secret.key" ]; then
                echo -ne "  ${ICON_WARN} ${YELLOW}Existing Playit key found. Reset it? (y/N) ${NC}"
                read reset_playit
                if [[ $reset_playit =~ ^[Yy]$ ]]; then
                    rm -f data/playit_secret.key
                    echo -e "  ${ICON_CHECK} Playit key removed. A new claim link will be generated."
                fi
            fi
            
            echo -e "  ${ICON_CHECK} Services stopped. Proceeding with setup..."
            ;;
        2)
            echo -e "\n  ${BLUE}${ICON_GEAR} Updating code and rebuilding...${NC}"
            git pull || true
            # Detect compose command
            if docker compose version &> /dev/null; then
                COMPOSE_CMD="docker compose"
            elif command -v docker-compose &> /dev/null; then
                COMPOSE_CMD="docker-compose"
            else
                echo -e "  ${ICON_CROSS} ${RED}docker compose plugin not found.${NC}"
                exit 1
            fi
            $COMPOSE_CMD stop mc-bot &>/dev/null || true
            $COMPOSE_CMD up -d --build
            echo -e "\n  ${ICON_CHECK} ${GREEN}Update complete! Bot container has been rebuilt.${NC}"
            exit 0
            ;;
        3)
            echo -e "  Cancelled."
            exit 0
            ;;
        *)
            echo -e "  ${BLUE}Proceeding with full reconfigure...${NC}"
            docker stop mc-bot &>/dev/null || true
            ;;
    esac
fi

# ---------------------------------------------------------
# 1. Check & Install Dependencies
# ---------------------------------------------------------
echo -e "\n${BLUE}${BOLD}${ICON_BOX} [1/4] Checking system dependencies...${NC}"

PKGS="git curl wget jq unzip tar openssl"
MISSING_PKGS=""
for pkg in $PKGS; do
    if command -v "$pkg" &> /dev/null; then
        echo -e "    ${ICON_CHECK} $pkg"
    else
        echo -e "    ${ICON_CROSS} $pkg ${DIM}(missing)${NC}"
        MISSING_PKGS="$MISSING_PKGS $pkg"
    fi
done

if [ -n "$MISSING_PKGS" ]; then
    echo -e "\n  ${ICON_WARN} ${YELLOW}Missing required base packages: $MISSING_PKGS${NC}"
    
    if [ "$EUID" -ne 0 ] && [ -z "$SUDO" ]; then
        echo -e "  ${ICON_CROSS} ${RED}Automated installation requires 'sudo' or root privileges.${NC}"
        echo -e "  Please run this script as root or install the following packages manually:"
        echo -e "    $MISSING_PKGS"
        exit 1
    fi

    echo -e "  ${BLUE}Installing required packages...${NC}"
    if command -v apt-get &> /dev/null; then
        $SUDO apt-get update && $SUDO apt-get install -y $MISSING_PKGS
    elif command -v dnf &> /dev/null; then
        $SUDO dnf install -y $MISSING_PKGS
    elif command -v pacman &> /dev/null; then
        $SUDO pacman -Sy --noconfirm $MISSING_PKGS
    elif command -v apk &> /dev/null; then
        $SUDO apk add $MISSING_PKGS
    else
        echo -e "  ${ICON_CROSS} ${RED}Could not detect a supported package manager (apt, dnf, pacman, apk).${NC}"
        echo -e "  Please install the missing packages manually: $MISSING_PKGS"
        exit 1
    fi
fi


# Function to securely install Docker with basic integrity validation
install_docker_securely() {
    DOCKER_SCRIPT_URL="https://get.docker.com"
    DOCKER_SCRIPT_PATH="get-docker.sh"
    
    echo -e "  ${BLUE}Downloading Docker install script...${NC}"
    curl -fsSL "$DOCKER_SCRIPT_URL" -o "$DOCKER_SCRIPT_PATH"
    
    # Basic integrity check: Does it look like a shell script?
    if ! head -n 1 "$DOCKER_SCRIPT_PATH" | grep -q "^#!/bin/sh"; then
        echo -e "  ${ICON_CROSS} ${RED}Downloaded Docker script is not a valid shell script. Aborting.${NC}"
        rm "$DOCKER_SCRIPT_PATH"
        exit 1
    fi
    
    echo -e "  ${BLUE}Executing Docker install script...${NC}"
    $SUDO sh "$DOCKER_SCRIPT_PATH"
    rm "$DOCKER_SCRIPT_PATH"
    
    echo -e "  ${BLUE}Enabling and starting Docker service...${NC}"
    if command -v systemctl &> /dev/null && pidof systemd &> /dev/null; then
        $SUDO systemctl enable --now docker
    elif command -v service &> /dev/null; then
        $SUDO service docker start || true
        sleep 3
    else
        echo -e "  ${ICON_WARN} ${YELLOW}Could not automatically start Docker. Please ensure the daemon is running.${NC}"
    fi
    echo -e "  ${ICON_CHECK} ${GREEN}Docker installed.${NC}"
}

if ! command -v docker &> /dev/null; then
    echo -e "\n  ${ICON_WARN} ${YELLOW}Docker is not installed.${NC}"
    read -p "    > Install Docker automatically? (y/N) " install_docker
    if [[ $install_docker =~ ^[Yy]$ ]]; then
        install_docker_securely
    else
        echo -e "  ${ICON_CROSS} ${RED}Docker is required.${NC}"
        exit 1
    fi
fi

# Ensure user is in the docker group to avoid permission issues
if ! groups "$TARGET_USER" | grep -q '\bdocker\b'; then
    echo -e "\n  ${ICON_WARN} ${YELLOW}User $TARGET_USER is not in the 'docker' group.${NC}"
    echo -e "  This is required to manage Docker without 'sudo' on every command.${NC}"
    read -p "    > Add user $TARGET_USER to the 'docker' group automatically? (Y/n) " add_to_group
    
    if [[ -z "$add_to_group" || $add_to_group =~ ^[Yy]$ ]]; then
        echo -e "  ${BLUE}Adding user $TARGET_USER to docker group...${NC}"
        $SUDO usermod -aG docker "$TARGET_USER"
        
        echo -e "\n  ${ICON_CHECK} ${GREEN}User '$TARGET_USER' added to 'docker' group.${NC}"
        echo -e "  ${ICON_LINK} ${BOLD}Applying permissions and continuing setup...${NC}"
        
        # Immediate update without logout
        if [ "$USER" = "root" ]; then
            exec su -c "$SCRIPT_DIR/$(basename "$0") $ORIG_ARGS" "$TARGET_USER"
        else
            exec sg docker -c "$SCRIPT_DIR/$(basename "$0") $ORIG_ARGS"
        fi
        exit 0
    else
        echo -e "  ${ICON_CROSS} ${RED}Manual action required: Add $TARGET_USER to the 'docker' group.${NC}"
        echo -e "  Run: sudo usermod -aG docker $TARGET_USER"
        exit 1
    fi
fi


# ---------------------------------------------------------
# 2. Configure Environment
# ---------------------------------------------------------
echo -e "\n${BLUE}${BOLD}${ICON_GEAR} [2/4] Configuring Environment...${NC}"

if [ -f .env ]; then
    echo -e "    ${ICON_CHECK} .env file already exists."
    read -p "    > Reconfigure? (y/N) " reconfig
    if [[ ! $reconfig =~ ^[Yy]$ ]]; then
        SKIP_CONFIG=1
    fi
fi

if [ -z "$SKIP_CONFIG" ]; then
    # Discord Token
    echo -e "\n  ${ICON_KEY} ${BOLD}Discord Bot Token${NC}"
    echo -e "    ${DIM}Get it from: https://discord.com/developers/applications${NC}"
    read -p "    > " BOT_TOKEN
    
    if [ -z "$BOT_TOKEN" ]; then
        echo -e "  ${ICON_CROSS} ${RED}Token required.${NC}"
        exit 1
    fi

    # Playit.gg
    echo -e "\n  ${ICON_LINK} ${BOLD}Playit.gg Tunneling${NC}"
    echo -e "    ${DIM}Free public access — no port forwarding needed.${NC}"
    read -p "    > Enable Playit.gg? [Y/n] " setup_playit

    PLAYIT_KEY=""
    if [[ -z "$setup_playit" || $setup_playit =~ ^[Yy]$ ]]; then
        echo -e "\n    Do you already have a ${CYAN}Playit Secret Key${NC}? [y/N]"
        echo -e "    ${DIM}(If this is your first time, just press Enter)${NC}"
        read -p "    > " has_key
        
        if [[ $has_key =~ ^[Yy]$ ]]; then
            echo -e "    Enter your ${CYAN}Playit Secret Key${NC}:"
            read -p "    > " PLAYIT_KEY
            
            if [ -n "$PLAYIT_KEY" ]; then
                mkdir -p data
                echo "$PLAYIT_KEY" > data/playit_secret.key
                chmod 600 data/playit_secret.key
                echo -e "    ${ICON_CHECK} ${GREEN}Secret key saved.${NC}"
            fi
        else
            echo -e "\n    ${ICON_CHECK} ${GREEN}Claim link will be generated after startup.${NC}"
        fi
    fi

    # Generate RCON
    RCON_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)

    # Docker sometimes creates .env as a root-owned directory if it's mounted before it exists.
    if [ -d .env ]; then
        echo -e "  ${ICON_WARN} ${YELLOW}.env is a directory. Removing it...${NC}"
        $SUDO rm -rf .env
    fi

    # Write .env
    PUID=$(id -u "$TARGET_USER")
    PGID=$(id -g "$TARGET_USER")

    cat > .env <<EOF
# Generated by install.sh
BOT_TOKEN=$BOT_TOKEN
RCON_PASSWORD=$RCON_PASSWORD
PLAYIT_SECRET_KEY=$PLAYIT_KEY
PUID=$PUID
PGID=$PGID
EOF
    $SUDO chown "$TARGET_USER:$TARGET_USER" .env
    $SUDO chmod 600 .env
    echo -e "\n  ${ICON_CHECK} ${GREEN}Configuration saved to .env${NC}"
fi

# ---------------------------------------------------------
# 3. Create Directories
# ---------------------------------------------------------
echo -e "\n${BLUE}${BOLD}${ICON_BOX} [3/4] Preparing directories...${NC}"
mkdir -p mc-server backups logs data
$SUDO chown -R "$TARGET_USER:$TARGET_USER" mc-server backups logs data
echo -e "    ${ICON_CHECK} mc-server, backups, logs, data ready."

# ---------------------------------------------------------
# 4. Docker Compose Up
# ---------------------------------------------------------
echo -e "\n${BLUE}${BOLD}${ICON_ROCKET} [4/4] Starting Services...${NC}"

# Detect compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "  ${ICON_CROSS} ${RED}docker compose plugin not found.${NC}"
    exit 1
fi

if [ "$SKIP_START" -eq 1 ]; then
    echo -e "  ${ICON_INFO} ${YELLOW}Skipping container startup due to --skip-start flag.${NC}"
else
    echo -e "  Building and starting containers..."
    echo -e "  ${DIM}This may take a few minutes for the first run...${NC}\n"
    $COMPOSE_CMD up -d --build

    # Setup Playit Claim Flow
    if [[ -z "$setup_playit" || $setup_playit =~ ^[Yy]$ ]] && [ -z "$PLAYIT_KEY" ]; then
        echo -e "\n${BLUE}${BOLD}${ICON_LINK} [5/5] Setting up Playit Tunnel...${NC}"

        if [ -s "data/playit_secret.key" ]; then
            echo -e "    ${ICON_CHECK} Playit secret key already exists. Skipping claim flow."
            SECRET_KEY=$(cat data/playit_secret.key)
        else
            # Give the container a moment to initialize before calling playit
            echo -ne "    Waiting for container to be ready..."
            for i in $(seq 1 30); do
                STATUS=$(docker inspect --format='{{.State.Status}}' mc-bot 2>/dev/null)
                if [ "$STATUS" = "running" ]; then
                    echo -e " ${GREEN}${ICON_CHECK}${NC}"
                    sleep 3
                    break
                fi
                echo -ne "."
                sleep 2
            done
            if [ "$STATUS" != "running" ]; then
                echo -e "\n  ${ICON_CROSS} ${RED}Container failed to start. Check: docker compose logs mc-bot${NC}"
                exit 1
            fi

            # Generate a claim code inside the container and build the URL
            echo -e "    Generating claim code..."
            CLAIM_CODE=$(docker exec mc-bot playit-cli claim generate 2>/dev/null | tail -1 | awk '{print $NF}') || true
            
            # Strict validation: Playit claim codes are usually 10 alphanumeric characters
            if [[ ! "$CLAIM_CODE" =~ ^[a-zA-Z0-9]{8,12}$ ]]; then
                echo -e "  ${ICON_CROSS} ${RED}Failed to generate a valid claim code.${NC}"
                echo -e "    ${DIM}Debug: Received '${CLAIM_CODE}' from playit-cli${NC}"
                echo -e "    Check if the container is running: ${CYAN}docker ps${NC}"
                echo -e "    Check container logs: ${CYAN}docker logs mc-bot${NC}"
                exit 1
            fi

            CLAIM_URL="https://playit.gg/claim/${CLAIM_CODE}"

                echo -e ""
                echo -e "    ${MAGENTA}${BOLD}┌────────────────────────────────────────────────────────────────────┐${NC}"
                echo -e "    ${MAGENTA}${BOLD}│${NC}  ${ICON_LINK} ${BOLD}Action Required: Claim your tunnel                        ${MAGENTA}${BOLD}│${NC}"
                echo -e "    ${MAGENTA}${BOLD}├────────────────────────────────────────────────────────────────────┤${NC}"
                echo -e "    ${MAGENTA}${BOLD}│${NC}  1. Open: ${CYAN}${BOLD}${CLAIM_URL}${NC}  ${MAGENTA}${BOLD}│${NC}"
                echo -e "    ${MAGENTA}${BOLD}│${NC}  2. Log in and click ${CYAN}CLAIM${NC}                                   ${MAGENTA}${BOLD}│${NC}"
                echo -e "    ${MAGENTA}${BOLD}│${NC}  ${DIM}Waiting for you to complete the claim...${NC}                  ${MAGENTA}${BOLD}│${NC}"
                echo -e "    ${MAGENTA}${BOLD}└────────────────────────────────────────────────────────────────────┘${NC}"
                echo -e ""

                # Exchange the claim code for a secret key (waits until browser claim is done)
                # We use tr to strictly clean the key of any hidden whitespace or newlines
                SECRET_KEY=$(docker exec mc-bot playit-cli claim exchange --wait 0 "$CLAIM_CODE" 2>&1 | tail -1 | awk '{print $NF}' | tr -d '\r\n ') || true

                if [ -z "$SECRET_KEY" ]; then
                    echo -e "  ${ICON_CROSS} ${RED}Did not receive a secret key from Playit.${NC}"
                else
                    echo "$SECRET_KEY" > data/playit_secret.key
                    chmod 600 data/playit_secret.key
                    echo -e "    ${ICON_CHECK} ${GREEN}Agent claimed successfully.${NC}"
                fi
        fi

        if [ -n "$SECRET_KEY" ]; then
            # Start the agent first so it registers with the Playit API
            echo -e "    Starting Playit agent..."
            docker exec mc-bot tmux kill-session -t playit 2>/dev/null || true
            docker exec mc-bot tmux new-session -d -s playit "bash -c 'playit --platform-docker --secret-path /app/data/playit_secret.key --socket-path /app/data/playit.sock -l /app/logs/playit.log'"
            # Increase sleep to ensure registration
            sleep 10

            # Auto-create Minecraft Java tunnel via REST API v1
            echo -e "    Creating Minecraft Java tunnel (port 25565)..."
            AGENT_DATA=$(docker exec mc-bot curl -s -X POST \
                -H "authorization: Agent-Key ${SECRET_KEY}" \
                -H "content-type: application/json" \
                -d '{}' \
                https://api.playit.gg/v1/agents/rundata) || true

            AGENT_ID=$(echo "$AGENT_DATA" | jq -r '.data.agent_id' 2>/dev/null) || true
            TUNNEL_COUNT=$(echo "$AGENT_DATA" | jq '.data.tunnels | length' 2>/dev/null) || echo 0

            if [ -z "$AGENT_ID" ] || [ "$AGENT_ID" = "null" ]; then
                echo -e "    ${ICON_WARN} ${YELLOW}Could not fetch agent ID. Tunnel creation skipped.${NC}"
            elif [ "$TUNNEL_COUNT" -gt 0 ]; then
                echo -e "    ${ICON_CHECK} ${GREEN}Agent already has $TUNNEL_COUNT tunnel(s). Using existing setup.${NC}"
            else
                echo -e "    Creating Minecraft Java tunnel (port 25565)..."
                TUNNEL_RESULT=$(docker exec mc-bot curl -s -X POST \
                    -H "authorization: Agent-Key ${SECRET_KEY}" \
                    -H "content-type: application/json" \
                    -d "{
  \"name\": \"minecraft\",
  \"tunnel_type\": \"minecraft-java\",
  \"port_type\": \"both\",
  \"port_count\": 1,
  \"origin\": {
    \"type\": \"agent\",
    \"data\": {
      \"agent_id\": \"${AGENT_ID}\",
      \"local_ip\": \"127.0.0.1\",
      \"local_port\": 25565
    }
  },
  \"enabled\": true
}" https://api.playit.gg/tunnels/create 2>/dev/null) || true

                if echo "$TUNNEL_RESULT" | grep -q '"status":"success"'; then
                    echo -e "    ${ICON_CHECK} ${GREEN}Minecraft Java tunnel created automatically.${NC}"
                else
                    echo -e "    ${ICON_WARN} ${YELLOW}Tunnel creation failed. Please create it manually at playit.gg${NC}"
                fi
            fi
        fi

    elif [ -s "data/playit_secret.key" ]; then
        # Already have a key from .env or previous install — just start the agent
        echo -e "    Starting Playit agent with existing secret key..."
        SECRET_KEY=$(cat data/playit_secret.key)
        docker exec mc-bot tmux kill-session -t playit 2>/dev/null || true
        docker exec mc-bot tmux new-session -d -s playit "bash -c 'playit --platform-docker --secret-path /app/data/playit_secret.key --socket-path /app/data/playit.sock -l /app/logs/playit.log'"
    fi
fi

# ---------------------------------------------------------
# Final Success Message
# ---------------------------------------------------------
echo -e "\n${GREEN}${BOLD}  ──────────────────────────────────────────${NC}"
echo -e "${GREEN}${BOLD}     ${ICON_ROCKET} Installation Complete!${NC}"
echo -e "${GREEN}${BOLD}  ──────────────────────────────────────────${NC}\n"

echo -e "  Your bot should be online in Discord shortly."
echo -e "  ${BOLD}Next Step:${NC} Run ${CYAN}/setup${NC} in Discord to initialize channels.\n"

echo -e "  ${BOLD}Useful Commands:${NC}"
echo -e "    ${DIM}View Logs:${NC}         ${CYAN}$COMPOSE_CMD logs -f mc-bot${NC}"
echo -e "    ${DIM}View Playit Logs:${NC}  ${CYAN}docker exec mc-bot cat /app/logs/playit.log${NC}"
echo -e "    ${DIM}Restart Bot:${NC}       ${CYAN}$COMPOSE_CMD restart mc-bot${NC}\n"

echo -e "  ${DIM}Thank you for using Minecraft Discord Bot!${NC}\n"
