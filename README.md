# Minecraft Discord Bot

A self-hosted Discord bot that gives you full control over your private Minecraft server.

## 📥 Installation

### 1. Requirements
- **Python 3.11** or newer.
- **Java** (Release 17-21 depending on your Minecraft version).

### 2. Setup
1. **Download** the bot files.
2. Open a terminal in the folder.
3. Run the installer:
   ```bash
   python install.py
   ```
   *This will automatically detect if you are on Windows or Linux/macOS and set up the environment.*

### 3. Configuration
- The installer will ask for your **Discord Bot Token**.
- You can manually edit `.env` later if needed.

### 4. Running
To start the bot:
```bash
python bot.py
```

## ✨ Features

### Server Control
- **Start / Stop / Restart**: Buttons in the control channel.
- **Console**: View the live server log and standard output in `#console`.
- **RCON**: Run commands like `/cmd op PlayerName`.

### Gameplay
- **Stats**: Check playtime and deaths with `/stats <player>`.
- **Online Players**: Bot status shows "Playing Minecraft: X Players".
- **Economy**: Earn fake coins with `/pay` or winning "Word Hunt" games.

### Tools
- **Backups**: create a backup zip and get a download link with `/backup`.
- **System Info**: See CPU/RAM usage with `/info`.
- **AI**: Chat with Grok using `/ai` (Requires API Key).

## ❓ FAQ

**Q: Where is `config.json`?**
A: We use `data/bot_config.json` for bot data. If you have an old `config.json`, it is backed up in `.backups/old`.

**Q: Can I run this on a server?**
A: Yes! Use `python install.py` on Linux and it will set up a virtual environment for you.

**Q: How do I update?**
A: `git pull` the latest changes and run `python install.py` again to check dependencies.
