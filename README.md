# Minecraft Discord Bot 🎮

A powerful Discord bot to manage your Minecraft server directly from Discord. Start, stop, monitor, and control your server with simple slash commands.

## ✨ Features

- **Server Control** - Start, stop, restart your Minecraft server
- **Real-time Monitoring** - Player list, server status, resource usage
- **Automated Tasks** - Scheduled backups, crash detection, auto-restarts
- **Role-Based Permissions** - Fine-grained access control per Discord role
- **RCON Integration** - Execute server commands directly from Discord
- **Statistics** - View player stats and server info

---

## 🚀 Quick Start (Docker - Recommended)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- **Windows users**: [WSL](https://aka.ms/wsl) installed (Docker runs in WSL)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/slogiker/mc-bot.git
   cd mc-bot
   ```

2. **Start the bot**
   
   **Linux/Mac:**
   ```bash
   ./start.sh
   ```
   
   **Windows:**
   ```batch
   start.bat
   ```
   (Double-click `start.bat` or run it from command prompt)
   
   The script will:
   - Prompt you for your Discord Bot Token
   - Auto-generate a secure RCON password
   - Build and start the Docker container (Python 3.11 + Java 21)

3. **Run setup in Discord**
   - Invite the bot to your server
   - Run `/setup` to create channels and roles

That's it! 🎉

---

## 📖 Common Commands

### Viewing Logs
```bash
docker-compose logs -f mc-bot
```

### Stopping the Bot
```bash
docker-compose down
```

### Restarting the Bot
```bash
docker-compose restart
```

### Rebuilding
```bash
docker-compose up -d --build
```

---

## 🎮 Discord Commands

All commands are slash commands. Run `/help` in Discord to see the full list.

**Server Management:**
- `/start` - Start the Minecraft server
- `/stop` - Stop the server safely
- `/restart` - Restart the server

**Information:**
- `/status` - Server status, players, resources
- `/players` - List online players
- `/stats [username]` - View player statistics
- `/version` - Server version info

**Admin:**
- `/backup_now` - Create immediate backup
- `/cmd [command]` - Execute RCON command
- `/whitelist_add [username]` - Add player to whitelist

---

## ⚙️ Configuration

The bot automatically configures itself on first run. Configuration is stored in:
- `.env` - Discord token and RCON password
- `config.json` - Server paths, channel IDs, role permissions

After running `/setup` in Discord, the bot will auto-configure channel and role IDs.

### Manual Configuration (Optional)

Edit `config.json` to customize:
- Server directory and Java settings
- Backup schedule and retention
- Restart schedule
- Role permissions

---

## 📁 Project Structure

```
mc-bot/
├── bot.py              # Main entry point
├── cogs/               # Discord command modules
├── src/                # Core utilities
├── config.json         # Bot configuration
├── .env                # Credentials (auto-created)
├── start.sh            # Docker startup script (Linux/Mac)
├── start.bat           # Docker startup script (Windows/WSL)
├── docs/               # Additional documentation
└── scripts/            # Installation scripts
```

---

## 🐳 Adding Minecraft Server (Optional)

If you want to run an actual Minecraft server with the bot:

1. Download Minecraft server jar from [minecraft.net](https://www.minecraft.net/download/server)
2. Place in `mc-server/` folder as `server.jar`
3. Create `mc-server/eula.txt` with: `eula=true`
4. Use `/start` command in Discord

---

## 📚 Documentation

- **[Docker Setup](docs/DOCKER.md)** - Detailed Docker documentation
- **[Local Installation](docs/LOCAL_INSTALL.md)** - Non-Docker setup guide
- **[Dry-Run Mode](docs/DRY_RUN.md)** - Testing and development mode

---

## 🛠️ Troubleshooting

**Bot won't start?**
```bash
docker-compose logs mc-bot
```

**Port already in use?**
```bash
sudo netstat -tulpn | grep -E '25565|25575'
```

**Need to reconfigure?**
- **Linux/Mac**: Delete `.env` and run `./start.sh` again
- **Windows**: Delete `.env` and run `start.bat` again

---

## 📝 Technical Details

- **Python**: 3.11
- **Java**: 21 (OpenJDK)
- **Discord.py**: Latest
- **Container**: Docker + Docker Compose
- **Ports**: 25565 (Minecraft), 25575 (RCON)
- **Memory**: 8GB limit (configurable)

---

## 🤝 Credits

Originally created by **slogiker**. Refactored and dockerized for ease of use.

---

## 📄 License

See repository for license information.
