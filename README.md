# Minecraft Discord Bot

A self-hosted Discord bot that brings your private Minecraft Java Server to life.

I built this because I was tired of SSH-ing into my server just to manage it. This bot runs alongside your Minecraft server in Docker, giving you full control via a clean Discord interface.

![Python](https://img.shields.io/badge/Python-3.11-blue) ![Docker](https://img.shields.io/badge/Docker-Required-blue)

---

## ⚡ Core Features

- **Control**: Start, Stop, Restart your server directly from a sticky interactive Control Panel in Discord.
- **No Port Forwarding**: Integrated **Playit.gg** support for instant public access with automatic IP fetching (`/info`).
- **Live Logs**: Stream the server console directly to a Discord channel.
- **Backups**: Automated daily backups with manual triggers.
- **Permissions**: Granular control over who can do what (Mods vs Admins).
- **Fun**: Economy system, chat minigames, and AI-powered MOTDs.

---

## 📥 Installation

This project is built for **Docker**. It works natively on Linux and Windows (WSL).

### 1. Requirements

- **Docker Installed**
- **Discord Bot Token**: Create an application at the [Discord Developer Portal](https://discord.com/developers/applications), create a Bot with right permissions, and copy the **Token**.

### 2. Setup (Linux / Standard)

The standard way to run this is via Docker Compose.

```bash
git clone https://github.com/slogiker/mc-bot.git
cd mc-bot

# Configure your environment
cp .env.example .env
nano .env
```

**Inside `.env`**:

- `BOT_TOKEN`: **Required.** Paste your Discord Bot Token here.
- `PLAYIT_SECRET_KEY`: (Optional) Paste your key from [playit.gg](https://playit.gg) if you want public access.
- `RCON_PASSWORD`: Leave this or change it. It's auto-configured for you internally, so you rarely need to touch it.

### 3. Start

```bash
docker compose up -d
```

The bot will start, generate the Minecraft server files (if missing), and come online in Discord.

---

## 🪟 Windows Users (Convenience Script)

We included a helper script (`install/install.bat`) for Windows users. It essentially just ensures you have WSL/Docker set up and runs the commands above for you.

1.  Run `install/install.bat`.
2.  Paste your **Discord Token** when asked.
3.  The script handles the rest.

---

## 🌐 Remote Access (Playit.gg)

If you're hosting at home and don't want to mess with router ports:

1.  Get a **Secret Key** from [playit.gg](https://playit.gg) (create a Linux/Docker agent).
2.  Add it to your `.env` file: `PLAYIT_SECRET_KEY=...`
3.  Restart: `docker compose up -d`.
4.  In the Playit dashboard, create a tunnel to `mc-bot:25565`.
5.  Type `/info` or `/ip` in Discord. The bot will automatically fetch and display your live Playit.gg address!

---

## ⚙️ Configuration

Check the `data/` folder after the first run.

- `user_config.json`: Manage backup schedules, role permissions, and memory settings.
- `bot_config.json`: Internal state (channel IDs). Don't touch this.

---

## 📜 Commands & Docs

- **Commands**: See [docs/commands.md](docs/commands.md) for a list of `/start`, `/pay`, `/ip`, and others.
- **Developers**: See [docs/DEVELOPER.md](docs/DEVELOPER.md) for architecture and contribution guides.
- **Roadmap**: See [docs/TODO.md](docs/TODO.md) for future project plans.

---

## 🔒 Offline Mode Support

The bot supports offline mode servers by generating MD5 based UUIDs natively. To use offline mode, select 'No' for Online Mode during the `/setup` procedure. The whitelist function will then automatically use local UUID generation instead of checking Mojang servers.
