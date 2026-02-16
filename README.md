# 🎮 Minecraft Discord Bot

> A powerful, self-hosted Discord bot that brings your private Minecraft Java Server to life.  
> **Control. Monitor. Automate.**

![Version](https://img.shields.io/badge/Version-2.5.6-blue) ![Python](https://img.shields.io/badge/Python-3.11+-yellow) ![Docker](https://img.shields.io/badge/Docker-Supported-blue)

---

## 📖 Overview

This bot serves as a **bridge between Discord and your Minecraft Server**, giving you full control without needing to SSH into your server. It runs essentially as a wrapper around the Minecraft Java process, capturing logs in real-time and allowing you to execute commands from Discord.

### Why use this?

- **🔒 Private & Secure**: Self-hosted on your own machine. No external databases or web panels required.
- **⚡ performance**: Lightweight and fast, using `aiofiles` and `asyncio` for non-blocking operations.
- **🐋 Docker Native**: Designed to run in a container for perfect isolation and easy updates.
- **👻 Ghost Mode**: Try it out without installing anything using our built-in simulation.

---

## ✨ Key Features

| Category             | Features                                                                                                                                                                                                   |
| :------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **🕹️ Control**       | **Start / Stop / Restart** buttons directly in Discord. <br> **Console Streaming**: Live server logs in a dedicated channel. <br> **RCON**: Execute server commands (`/cmd`) remotely.                     |
| **📊 Stats & Info**  | **Live Status**: Bot status shows "Playing Minecraft: X Players". <br> **Player Stats**: Check playtime, deaths, and joins (`/stats`). <br> **System Health**: Monitor CPU, RAM, and Disk usage (`/info`). |
| **🤖 Automation**    | **Auto-Backups**: Scheduled world zipping and upload. <br> **Auto-Restarts**: Scheduled daily restarts. <br> **AI Integration**: Chat with Grok (`/ai`) and AI-generated MOTDs.                            |
| **💰 Economy & Fun** | **Economy System**: Earn coins, check balances (`/pay`). <br> **Minigames**: "Word Hunt" events in chat to earn coins. <br> **Events**: Schedule community events with auto-reminders.                     |

---

## 📥 Installation

### 1. Requirements

- **OS**: Windows 10/11 (with WSL2 support) OR Linux.
- **Docker**: Desktop (Windows) or Engine (Linux).
- **Discord Bot Token**: Get one from the [Discord Developer Portal](https://discord.com/developers/applications).

### 🚀 Option A: Windows (One-Click)

We provide a "magic" installer that handles WSL, Docker, and dependencies for you.

1.  **Download** the repository.
2.  Double-click `install/install.bat`.
3.  Follow the on-screen prompts.
    - It will ask for your **Discord Token**.
    - It will generate a secure **RCON Password**.

### 🐧 Option B: Linux / Manual

If you prefer manual setup or are running on a Linux VPS:

```bash
# Clone the repo
git clone https://github.com/yourusername/mc-bot.git
cd mc-bot

# Make installer executable
chmod +x install/install.sh

# Run setup
sudo ./install/install.sh
```

---

## 👻 Ghost Mode (Try it safely!)

Want to see how the installation looks or test the bot commands **without** modifying your system or starting a real server?

Run the simulation script:

```bash
python install/simulate.py
```

- **Safe**: No files created, no Docker containers spawned.
- **Realistic**: Mimics the exact installation process visually.
- **Interactive**: You can use `/start`, `/stop`, and other commands in Discord to see the bot's responses.

---

## ⚙️ Configuration

The bot uses a **clean file-based configuration** located in the `data/` folder.

- **`data/user_config.json`**:
  - Manage **backups** (time, retention).
  - Manage **permissions** (which Discord roles can control the server).
  - Manage **Java RAM** settings (Min/Max).

- **`.env`**:
  - Stores secrets like `BOT_TOKEN` and `RCON_PASSWORD`.

- **`data/bot_config.json`**:
  - Stores internal state (Channel IDs, Guild ID). _Avoid editing this manually unless necessary._

---

## 📚 Advanced Documentation

For developers or power users who want to understand the code structure, Docker volumes, or contribute, check out the full **Developer Documentation**:

👉 **[Read DEVELOPER.md](docs/DEVELOPER.md)**

---

## ❓ FAQ

**Q: Where are my backups stored?**
A: In the `backups/` folder in the root directory.

**Q: Can I change specific permissions?**
A: Yes! Edit `data/user_config.json` to assign specific commands to your Discord roles.

**Q: It says "PyNaCl is not installed"?**
A: This is only needed for Voice features (not yet implemented). You can ignore this warning.
