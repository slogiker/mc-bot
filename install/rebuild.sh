#!/bin/bash

# Developer Rebuild Script
# Rebuilds Docker image without cache after code changes

set -e

# ANSI Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect if we're running from install/ subdirectory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "$SCRIPT_DIR")" == "install" ]]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_ROOT"
fi

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}   Developer Rebuild - MC Bot${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Check if git is available
if command -v git &> /dev/null; then
    # Check if we're in a git repository
    if git rev-parse --git-dir > /dev/null 2>&1; then
        echo -e "${BLUE}[GIT] Checking repository status...${NC}"
        
        # Fetch latest changes from remote (quietly)
        git fetch --quiet
        
        # Check if we're behind the remote
        LOCAL=$(git rev-parse @)
        REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "")
        
        if [ -z "$REMOTE" ]; then
            echo -e "${YELLOW}[WARN] No upstream branch found. Skipping git check.${NC}"
        elif [ "$LOCAL" != "$REMOTE" ]; then
            BASE=$(git merge-base @ @{u})
            
            if [ "$LOCAL" = "$BASE" ]; then
                echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
                echo -e "${YELLOW}║  WARNING: Your local branch is behind the remote!         ║${NC}"
                echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
                echo ""
                echo -e "  ${CYAN}There are new commits on the remote that you haven't pulled.${NC}"
                echo ""
                echo -e "  ${GREEN}Recommended action:${NC}"
                echo -e "    ${CYAN}git pull${NC}"
                echo ""
                read -p "  Do you want to continue rebuilding anyway? (y/N): " CONTINUE
                
                if [[ ! $CONTINUE =~ ^[Yy]$ ]]; then
                    echo -e "${YELLOW}[CANCEL] Rebuild cancelled. Please pull latest changes first.${NC}"
                    exit 0
                fi
            elif [ "$REMOTE" = "$BASE" ]; then
                echo -e "${GREEN}[OK] Local branch is ahead of remote (you have unpushed commits)${NC}"
            else
                echo -e "${YELLOW}[WARN] Branches have diverged. Consider running 'git status'.${NC}"
            fi
        else
            echo -e "${GREEN}[OK] Repository is up to date with remote${NC}"
        fi
        echo ""
    fi
fi

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}[ERROR] Docker Compose is not installed or not in PATH.${NC}"
    exit 1
fi

echo -e "${BLUE}[STEP 1/3] Stopping existing containers...${NC}"
$DOCKER_COMPOSE_CMD down

echo ""
echo -e "${BLUE}[STEP 2/3] Rebuilding image (--no-cache)...${NC}"
echo -e "${YELLOW}[INFO] This will take a few minutes...${NC}"
$DOCKER_COMPOSE_CMD build --no-cache

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Build failed!${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}[STEP 3/3] Starting containers...${NC}"
$DOCKER_COMPOSE_CMD up -d

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to start containers!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Rebuild completed successfully! ✓                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo -e "  View logs:  ${CYAN}$DOCKER_COMPOSE_CMD logs -f mc-bot${NC}"
echo -e "  Stop:       ${CYAN}$DOCKER_COMPOSE_CMD down${NC}"
echo ""
