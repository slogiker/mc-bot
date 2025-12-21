#!/bin/bash

# Minecraft Discord Bot - Docker Startup Script
# Simple script to start the bot in Docker

set -e

echo "🚀 Minecraft Discord Bot - Docker Setup"
echo "========================================"
echo ""

# Check if .env exists and is configured
if [ ! -f .env ]; then
    echo "⚠️  .env file not found! Let's set it up..."
    echo ""
    
    # Prompt for Discord Bot Token
    echo "📝 Please enter your Discord Bot Token:"
    echo "   (Get it from: https://discord.com/developers/applications)"
    read -p "BOT_TOKEN: " bot_token
    
    # Validate token is not empty
    if [ -z "$bot_token" ]; then
        echo "❌ Bot token cannot be empty!"
        exit 1
    fi
    
    # Generate random RCON password
    rcon_password=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
    
    echo ""
    echo "🔐 Auto-generated RCON password: $rcon_password"
    echo ""
    
    # Create .env file
    cat > .env << EOF
# Discord Bot Configuration
BOT_TOKEN=$bot_token

# Minecraft RCON Password (auto-generated)
RCON_PASSWORD=$rcon_password
EOF
    
    echo "✅ Created .env file with your configuration!"
    echo ""
elif ! grep -q "BOT_TOKEN=." .env 2>/dev/null || ! grep -q "RCON_PASSWORD=." .env 2>/dev/null; then
    echo "⚠️  .env file exists but appears incomplete!"
    echo "📝 Please ensure .env contains:"
    echo "   - BOT_TOKEN=your_discord_bot_token"
    echo "   - RCON_PASSWORD=your_rcon_password"
    echo ""
    read -p "Do you want to reconfigure .env? (y/N): " reconfigure
    
    if [[ $reconfigure =~ ^[Yy]$ ]]; then
        # Backup existing .env
        cp .env .env.backup.$(date +%s)
        echo "📦 Backed up existing .env"
        
        # Prompt for Discord Bot Token
        echo ""
        echo "📝 Please enter your Discord Bot Token:"
        read -p "BOT_TOKEN: " bot_token
        
        if [ -z "$bot_token" ]; then
            echo "❌ Bot token cannot be empty!"
            exit 1
        fi
        
        # Generate random RCON password
        rcon_password=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
        
        echo ""
        echo "🔐 Auto-generated RCON password: $rcon_password"
        echo ""
        
        # Create .env file
        cat > .env << EOF
# Discord Bot Configuration
BOT_TOKEN=$bot_token

# Minecraft RCON Password (auto-generated)
RCON_PASSWORD=$rcon_password
EOF
        
        echo "✅ Updated .env file!"
        echo ""
    else
        echo "⚠️  Please configure .env manually and run this script again."
        exit 1
    fi
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p mc-server backups logs

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Start with docker-compose
echo ""
echo "🐳 Starting Docker containers..."
docker-compose up -d

echo ""
echo "✅ Bot started successfully!"
echo ""
echo "📊 Useful commands:"
echo "   View logs:        docker-compose logs -f mc-bot"
echo "   Stop bot:         docker-compose down"
echo "   Restart bot:      docker-compose restart"
echo "   Access shell:     docker-compose exec mc-bot bash"
echo "   Rebuild:          docker-compose up -d --build"
echo ""
