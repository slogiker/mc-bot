# Docker Setup Guide - Minecraft Discord Bot

Simple guide to run your Minecraft Discord Bot in Docker with Python 3.11 + Java 17.

## Prerequisites

- **Docker** installed ([Get Docker](https://docs.docker.com/get-docker/))
- **Docker Compose** installed (usually comes with Docker Desktop)

## Quick Start

### 1️⃣ Run the start script

```bash
chmod +x start.sh
./start.sh
```

The script will:
- Check if `.env` exists and create it if needed
- Create necessary directories (`mc-server`, `backups`, `logs`)
- Build and start the Docker container

### 2️⃣ Configure `.env` (first time only)

Edit `.env` and add your credentials:

```env
BOT_TOKEN=your_discord_bot_token_here
RCON_PASSWORD=your_rcon_password_here
```

### 3️⃣ Run again

```bash
./start.sh
```

## Manual Commands

### Build and Start
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f mc-bot
```

### Stop Bot
```bash
docker-compose down
```

### Restart Bot
```bash
docker-compose restart
```

### Rebuild Container
```bash
docker-compose up -d --build
```

### Access Container Shell
```bash
docker-compose exec mc-bot bash
```

## Persistent Data

The following directories are mounted as volumes and persist across container restarts:

- `./mc-server` → Minecraft server files
- `./backups` → Server backups
- `./logs` → Bot logs

## Ports

- **25565** - Minecraft server
- **25575** - RCON

## Memory Limit

The container is configured with an **8GB memory limit**. Adjust in `docker-compose.yml` if needed:

```yaml
mem_limit: 8g  # Change this value
```

## Configuration

The bot uses `/app/mc-server` as the Minecraft server directory inside the container. The `config.json` has been updated to use Docker paths:

- `server_directory`: `/app/mc-server`
- `java_path`: `java` (OpenJDK 17 installed in container)
- `rcon_host`: `127.0.0.1` (localhost)

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs mc-bot

# Check if ports are already in use
sudo netstat -tulpn | grep -E '25565|25575'
```

### Bot can't connect to Discord
- Check your `BOT_TOKEN` in `.env`
- Ensure `.env` file is in the project root

### Minecraft server won't start
- Ensure you have Minecraft server files in `./mc-server/`
- Check Java is working: `docker-compose exec mc-bot java -version`
- Check RCON password matches in `.env`

### Memory issues
- Increase memory limit in `docker-compose.yml`
- Adjust Java heap sizes in `config.json` (`java_xms`, `java_xmx`)

## First Time Setup

If you don't have Minecraft server files yet:

1. Download Minecraft server jar from [minecraft.net](https://www.minecraft.net/download/server)
2. Place it in `./mc-server/` as `server.jar`
3. Accept EULA: create `mc-server/eula.txt` with `eula=true`
4. Start the bot and use Discord commands to start the server
