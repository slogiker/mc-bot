#!/bin/bash

# Minecraft Discord Bot - Linux/Docker Installer
# ---------------------------------------------------
# This script handles:
# 1. Dependency checks (Docker, Git)
# 2. Environment configuration (.env)
# 3. Docker container deployment

set -e

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

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Ensure we are in the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "$SCRIPT_DIR")" == "install" ]]; then
    cd "$(dirname "$SCRIPT_DIR")"
fi

echo -e "${CYAN}---------------------------------------------${NC}"
echo -e "${CYAN}   Minecraft Discord Bot - Linux Installer   ${NC}"
echo -e "${CYAN}---------------------------------------------${NC}"
echo ""

# Detect existing installation
if [ -f .env ] && command -v docker &> /dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^mc-bot$'; then
    echo -e "${YELLOW}An existing installation was detected (running mc-bot container found).${NC}"
    echo ""
    echo -e "  ${CYAN}1)${NC} Reconfigure & Reinstall (fresh setup)"
    echo -e "  ${CYAN}2)${NC} Update code only (git pull + rebuild)"
    echo -e "  ${CYAN}3)${NC} Cancel"
    echo ""
    read -p "Choose an option [1/2/3]: " INSTALL_MODE
    case $INSTALL_MODE in
        2)
            echo -e "${BLUE}Updating code and rebuilding...${NC}"
            git pull || true
            # Detect compose command
            if docker compose version &> /dev/null; then
                COMPOSE_CMD="docker compose"
            elif command -v docker-compose &> /dev/null; then
                COMPOSE_CMD="docker-compose"
            else
                echo -e "${RED}[ERROR] docker compose plugin not found.${NC}"
                exit 1
            fi
            $COMPOSE_CMD up -d --build
            echo -e "${GREEN}[OK] Update complete! Bot container has been rebuilt.${NC}"
            exit 0
            ;;
        3)
            echo -e "Cancelled."
            exit 0
            ;;
        *)
            echo -e "${BLUE}Proceeding with full reconfigure...${NC}"
            ;;
    esac
fi

# 1. Check & Install Dependencies
echo -e "${BLUE}[1/4] Checking dependencies...${NC}"

if ! command -v git &> /dev/null || ! command -v curl &> /dev/null || ! command -v wget &> /dev/null || ! command -v jq &> /dev/null || ! command -v unzip &> /dev/null || ! command -v tar &> /dev/null || ! command -v openssl &> /dev/null; then
    echo -e "${YELLOW}[WARN] Missing some required base packages.${NC}"
    echo -e "${BLUE}Installing required packages (git, curl, wget, jq, unzip, tar, openssl)...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y git curl wget jq unzip tar openssl
    elif command -v apk &> /dev/null; then
        sudo apk add git curl wget jq unzip tar openssl
    else
        echo -e "${RED}[ERROR] Could not install packages automatically. Please install them manually.${NC}"
        exit 1
    fi
fi

if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}[WARN] Docker is not installed.${NC}"
    read -p "      > Install Docker automatically? (y/N) " install_docker
    if [[ $install_docker =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Installing Docker (using official script)...${NC}"
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        rm get-docker.sh
        
        echo -e "${BLUE}Enabling and starting Docker service...${NC}"
        if command -v systemctl &> /dev/null && pidof systemd &> /dev/null; then
            sudo systemctl enable --now docker
        elif command -v service &> /dev/null; then
            sudo service docker start || true
            sleep 3
        else
            echo -e "${YELLOW}[WARN] Could not automatically start Docker. Please ensure the daemon is running.${NC}"
        fi
        echo -e "${GREEN}[OK] Docker installed.${NC}"
    else
        echo -e "${RED}[ERROR] Docker is required.${NC}"
        exit 1
    fi
fi

# Ensure user is in the docker group to avoid permission issues
TARGET_USER=${SUDO_USER:-$USER}
if ! groups $TARGET_USER | grep -q '\bdocker\b'; then
    echo -e "${YELLOW}[WARN] User $TARGET_USER is not in the 'docker' group.${NC}"
    echo -e "${BLUE}Adding user $TARGET_USER to docker group...${NC}"
    sudo usermod -aG docker "$TARGET_USER" || true
    
    if [ "$USER" != "$TARGET_USER" ]; then
        sudo usermod -aG docker "$USER" || true
    fi

    echo -e "${GREEN}[OK] Added. Applying docker group permissions and continuing setup...${NC}"
    # The 'docker' group membership takes effect only after a new session.
    # To avoid requiring a manual log out/log in, the script re-executes itself
    # with the new group permissions applied.
    if [ "$USER" = "root" ]; then
        # If run as root, execute as the target user to apply docker group.
        exec su -c "$SCRIPT_DIR/$(basename "$0") $ORIG_ARGS" "$TARGET_USER"
    else
        # If run as non-root, execute within the docker group.
        exec sg docker -c "$SCRIPT_DIR/$(basename "$0") $ORIG_ARGS"
    fi
fi

# 2. Configure Environment
echo ""
echo -e "${BLUE}[2/4] Configuring Environment...${NC}"

if [ -f .env ]; then
    echo -e "${GREEN}[OK] .env file exists.${NC}"
    read -p "      > Reconfigure? (y/N) " reconfig
    if [[ ! $reconfig =~ ^[Yy]$ ]]; then
        SKIP_CONFIG=1
    fi
fi

if [ -z "$SKIP_CONFIG" ]; then
    # Discord Token
    echo ""
    echo -e "Enter your ${CYAN}Discord Bot Token${NC}:"
    echo -e "(Get it from https://discord.com/developers/applications)"
    read -p "> " BOT_TOKEN
    
    if [ -z "$BOT_TOKEN" ]; then
        echo -e "${RED}[ERROR] Token required.${NC}"
        exit 1
    fi

    # Playit.gg
    echo ""
    echo -e "Do you want to configure ${CYAN}Playit.gg${NC} for public access?"
    echo -e "(Free tunneling — no port forwarding needed)"
    read -p "> [Y/n] " setup_playit

    PLAYIT_KEY=""
    if [[ -z "$setup_playit" || $setup_playit =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "Do you already have a ${CYAN}Playit Secret Key${NC}? [y/N]"
        echo -e "(If this is your first time, just press Enter)"
        read -p "> " has_key
        
        if [[ $has_key =~ ^[Yy]$ ]]; then
            echo -e "Enter your ${CYAN}Playit Secret Key${NC}:"
            read -p "> " PLAYIT_KEY
            
            if [ -n "$PLAYIT_KEY" ]; then
                mkdir -p data
                echo "$PLAYIT_KEY" > data/playit_secret.key
                echo -e "${GREEN}[OK] Secret key saved.${NC}"
            fi
        else
            echo ""
            echo -e "${GREEN}✅ After startup, we'll generate a claim link for you.${NC}"
            echo -e "   Just open it in your browser and click ${CYAN}Claim${NC} — takes 30 seconds."
        fi
    fi

    # Generate RCON
    RCON_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)

    # Docker sometimes creates .env as a root-owned directory if it's mounted before it exists.
    if [ -d .env ]; then
        echo -e "${YELLOW}[WARN] .env is a directory (likely created by Docker). Removing it...${NC}"
        sudo rm -rf .env
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
    chown "$TARGET_USER:$TARGET_USER" .env
    chmod 600 .env
    echo -e "${GREEN}[OK] Configuration saved.${NC}"
fi

# 3. Create Directories
echo ""
echo -e "${BLUE}[3/4] Creating directories...${NC}"
mkdir -p mc-server backups logs data
chown -R "$TARGET_USER:$TARGET_USER" mc-server backups logs data
echo -e "${GREEN}[OK] Directories ready.${NC}"

# 4. Docker Compose Up
echo ""
echo -e "${BLUE}[4/4] Starting Services...${NC}"

# Detect compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}[ERROR] docker compose plugin not found.${NC}"
    exit 1
fi

if [ "$SKIP_START" -eq 1 ]; then
    echo -e "${YELLOW}[SKIP] Skipping container startup due to --skip-start flag.${NC}"
else
    echo -e "Building and starting containers..."
    $COMPOSE_CMD up -d --build

    # Setup Playit Claim Flow
    if [[ -z "$setup_playit" || $setup_playit =~ ^[Yy]$ ]] && [ -z "$PLAYIT_KEY" ]; then
        echo ""
        echo -e "${BLUE}[5/5] Setting up Playit Tunnel...${NC}"

        if [ -s "data/playit_secret.key" ]; then
            echo -e "${GREEN}[OK] Playit secret key already exists. Skipping claim flow.${NC}"
            SECRET_KEY=$(cat data/playit_secret.key)
        else
            # Give the container a moment to initialize before calling playit
            echo -e "Waiting for container to be ready..."
            for i in $(seq 1 30); do
                STATUS=$(docker inspect --format='{{.State.Status}}' mc-bot 2>/dev/null)
                if [ "$STATUS" = "running" ]; then
                    sleep 3
                    break
                fi
                sleep 2
            done
            if [ "$STATUS" != "running" ]; then
                echo -e "${RED}[ERROR] Container failed to start. Check: docker compose logs mc-bot${NC}"
                exit 1
            fi

            # Generate a claim code inside the container and build the URL
            echo -e "Generating claim code..."
            CLAIM_CODE=$(docker exec mc-bot playit-cli claim generate 2>&1 | tail -1 | awk '{print $NF}') || true
            
            if [[ -z "$CLAIM_CODE" || "$CLAIM_CODE" =~ [[:space:]] || ${#CLAIM_CODE} -gt 20 ]]; then
                echo -e "${RED}[ERROR] Invalid claim code from Playit. Got: '${CLAIM_CODE}'${NC}"
                echo "        Make sure the container is running and playit-cli binary is installed."
                exit 1
            fi

            CLAIM_URL="https://playit.gg/claim/${CLAIM_CODE}"

                echo -e ""
                echo -e "${YELLOW}======================================================================${NC}"
                echo -e "${GREEN}👉 Open this link in your browser:${NC}"
                echo -e "${CYAN}${CLAIM_URL}${NC}"
                echo -e "${GREEN}👉 Create a free account or log in, then click CLAIM.${NC}"
                echo -e "${YELLOW}Waiting for you to claim the agent — this will complete automatically.${NC}"
                echo -e "${YELLOW}======================================================================${NC}"
                echo -e ""

                # Exchange the claim code for a secret key (waits until browser claim is done)
                SECRET_KEY=$(docker exec mc-bot playit-cli claim exchange --wait 0 "$CLAIM_CODE" 2>&1 | tail -1 | awk '{print $NF}') || true

                if [ -z "$SECRET_KEY" ]; then
                    echo -e "${RED}[ERROR] Did not receive a secret key from Playit. Try running the installer again.${NC}"
                else
                    echo "$SECRET_KEY" > data/playit_secret.key
                    echo -e "${GREEN}[OK] Agent claimed. Secret key saved.${NC}"
                fi
        fi

        if [ -n "$SECRET_KEY" ]; then
            # Start the agent first so it registers with the Playit API
            echo -e "Starting Playit agent..."
            docker exec mc-bot tmux kill-session -t playit 2>/dev/null || true
            docker exec mc-bot tmux new-session -d -s playit "bash -c 'playit --platform-docker --secret-path /app/data/playit_secret.key --socket-path /app/data/playit.sock -l /app/logs/playit.log'"
            sleep 8

            # Auto-create Minecraft Java tunnel via REST API v1
            echo -e "Creating Minecraft Java tunnel (port 25565)..."
            AGENT_DATA=$(docker exec mc-bot curl -s -X POST \
                -H "authorization: Agent-Key ${SECRET_KEY}" \
                -H "content-type: application/json" \
                -d '{}' \
                https://api.playit.gg/v1/agents/rundata) || true

            AGENT_ID=$(echo "$AGENT_DATA" | docker exec -i mc-bot jq -r '.data.agent_id' 2>/dev/null) || true

            if [ -z "$AGENT_ID" ] || [ "$AGENT_ID" = "null" ]; then
                echo -e "${YELLOW}[WARN] Could not fetch agent ID. Tunnel creation skipped — create it manually at https://playit.gg${NC}"
                echo "DEBUG: API response: $AGENT_DATA"
            else
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
                    echo -e "${GREEN}[OK] Minecraft Java tunnel created automatically.${NC}"
                elif echo "$TUNNEL_RESULT" | grep -q '"status":"error"'; then
                    FAIL_REASON=$(echo "$TUNNEL_RESULT" | docker exec -i mc-bot jq -r '.data.message // "Unknown error"')
                    echo -e "${YELLOW}[WARN] Tunnel creation returned: ${FAIL_REASON}. Create it manually at https://playit.gg${NC}"
                else
                    echo -e "${YELLOW}[WARN] Tunnel creation gave unexpected response. Create it manually at https://playit.gg${NC}"
                    echo "DEBUG: API response: $TUNNEL_RESULT"
                fi
            fi
        fi

    elif [ -s "data/playit_secret.key" ]; then
        # Already have a key from .env or previous install — just start the agent
        echo -e "Starting Playit agent with existing secret key..."
        SECRET_KEY=$(cat data/playit_secret.key)
        docker exec mc-bot tmux kill-session -t playit 2>/dev/null || true
        docker exec mc-bot tmux new-session -d -s playit "bash -c 'playit --platform-docker --secret-path /app/data/playit_secret.key --socket-path /app/data/playit.sock -l /app/logs/playit.log'"
    fi
fi

echo ""
echo -e "${GREEN}---------------------------------------------${NC}"
echo -e "${GREEN}   Setup Complete!   ${NC}"
echo -e "${GREEN}---------------------------------------------${NC}"
echo ""
echo -e "Your bot should be online in Discord."
echo -e "Run: ${CYAN}/setup${NC} in Discord to initialize channels."
echo ""
echo -e "To view bot logs:    ${CYAN}$COMPOSE_CMD logs -f mc-bot${NC}"
echo -e "To view Playit logs: ${CYAN}docker exec mc-bot cat /app/logs/playit.log${NC} (if configured)"