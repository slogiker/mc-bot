#!/bin/bash

# mc-bot.sh — Friendly CLI for managing the Minecraft Discord Bot
# Usage: ./mc-bot.sh [start|stop|restart|logs|update|status|clean]

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    exit 1
fi

case "$1" in
    start)
        echo -e "${BLUE}Starting MC-Bot...${NC}"
        docker compose up -d
        echo -e "${GREEN}Bot started in background.${NC}"
        ;;
    stop)
        echo -e "${YELLOW}Stopping MC-Bot...${NC}"
        docker compose stop
        echo -e "${GREEN}Bot stopped.${NC}"
        ;;
    restart)
        echo -e "${BLUE}Restarting MC-Bot...${NC}"
        docker compose restart
        echo -e "${GREEN}Bot restarted.${NC}"
        ;;
    logs)
        echo -e "${CYAN}Streaming logs (Ctrl+C to stop)...${NC}"
        docker compose logs -f
        ;;
    update)
        echo -e "${BLUE}Updating MC-Bot...${NC}"
        git pull origin main
        docker compose up -d --build
        echo -e "${GREEN}Bot updated and restarted.${NC}"
        ;;
    status)
        docker compose ps
        ;;
    clean)
        echo -e "${RED}Cleaning up containers and volumes...${NC}"
        docker compose down --rmi local --volumes
        echo -e "${GREEN}Cleanup complete.${NC}"
        ;;
    *)
        echo -e "${BOLD}MC-Bot CLI${NC}"
        echo -e "Usage: ./mc-bot.sh [command]"
        echo -e ""
        echo -e "Commands:"
        echo -e "  ${GREEN}start${NC}    - Start the bot"
        echo -e "  ${YELLOW}stop${NC}     - Stop the bot"
        echo -e "  ${BLUE}restart${NC}  - Restart the bot"
        echo -e "  ${CYAN}logs${NC}     - View live logs"
        echo -e "  ${BLUE}update${NC}   - Pull latest code and rebuild"
        echo -e "  ${NC}status${NC}   - Show container status"
        echo -e "  ${RED}clean${NC}    - Full reset (removes containers/images)"
        echo -e ""
        ;;
esac
