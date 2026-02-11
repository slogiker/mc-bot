# Developer Documentation

**Repository**: `mc-bot`
**Version**: v2.5.3
**Last Updated**: February 2026

---

## 📖 Overview

This is a **self-hosted Discord bot** designed to manage a local Minecraft Java Edition server. It acts as a bridge between Discord and the server process, providing remote control, monitoring, and automation features.

### Core Philosophy
- **Private Use**: Built for small friend groups, not public servers.
- **Self-Contained**: No external web panels or databases required (uses JSON/Filelock).
- **Direct Control**: Wraps the server JAR process (`subprocess`) and uses RCON for commands.

---

## 🛠️ Architecture Deep Dive

### Why this stack?
- **Python + discord.py**: rapid development of slash commands and asynchronous task management.
- **Subprocess**: The bot *is* the wrapper. It owns the Java process, capturing STDOUT directly for the log console.
- **Filelock**: We use multiple JSON files for persistent storage. Since the bot runs async tasks (log tailing, backups, commands) that might read/write config simultaneously, `filelock` prevents race conditions and data corruption.
- **Aiofiles**: Logging can be heavy. Reading `latest.log` line-by-line asynchronously prevents the bot from "freezing" while waiting for file I/O operations, keeping the Discord UI responsive.

### File Structure (v2.5.3)

| Path | Description |
| :--- | :--- |
| **Root** | |
| `bot.py` | Main entry point. Loads cogs, starts `TmuxServerManager`, handles shutdown signals. |
| `install.py` | Universal installer script. Detects OS and launches appropriate script from `scripts/`. |
| `.env` | **Secret** configuration (Discord Token, RCON Password, API Keys). |
| `requirements.txt` | Python dependencies. |
| **Scripts** | |
| `scripts/install-*.sh/ps1` | Platform-specific setup scripts (Java check, VEnv creation). |
| `scripts/start.bat` | Convenience launcher for Windows. |
| **Cogs (`cogs/`)** | **Discord Command Modules** |
| `console.py` | Live log streaming, Owner-only RCON (`/cmd`), Presence updates. |
| `stats.py` | Player stats (`/stats`). Parses NBT `.dat` files for offline players and hits Mojang API for online. |
| `info.py` | System health (`/info`). Uses `psutil` to check CPU/RAM/Disk usage of the host. |
| `backup.py` | Backup commands (`/backup`). Triggers zip creation and ephemeral uploads. |
| `economy.py` | Balance system (`/pay`) and background "Word Hunt" minigame. |
| `ai.py` | AI integration. Uses `xai-sdk` to chat with Grok (`/ai`) and generate MOTDs. |
| `events.py` | Scheduling system (`/event`) with auto-reminders (24h/1h). |
| `automation.py` | Background tasks: AI MOTD updates and custom Regex Chat Triggers. |
| `management.py` | Control panel commands (Start/Stop/Restart). |
| `setup.py` | Setup wizard for completely new installations. |
| **Src (`src/`)** | **Core Logic & Helpers** |
| `backup_manager.py` | Handles Zipping world folders and interacting with `pyonesend`. |
| `server_info_manager.py` | Updates the persistent "Status" channel embed. |
| `logger.py` | Centralized logging configuration. |
| `utils.py` | RCON wrapper, file helpers, role checkers. |
| **Utils (`utils/`)** | |
| `config.py` | **Thread-safe** `load/save` for JSON configs using `FileLock`. |
| **Data (`data/`)** | **Persistent Storage** |
| `bot_config.json` | Core bot state: Economy balances, Event lists, Setup flags. |
| `user_config.json` | User preferences: Custom triggers, Schedule settings. |

---

## ⚙️ Configuration Guide

### `bot_config.json` vs `user_config.json`
- **Bot Config**: Stores *system state* and *essential data* logic. (e.g. "Who has how much money?", "What events are scheduled?", "Where is the server jar?").
- **User Config**: Stores *user preferences* and *customizations*. (e.g. "What keyword triggers should the bot listent to?", "What time should backups run?").

### Environment Variables (.env)
- `DISCORD_TOKEN`: Required.
- `RCON_PASSWORD`: Required for sending commands (Generated automatically).
- `XAI_API_KEY`: Optional. Enables Grok features.
- `ONE_SEND_TOKEN`: Optional (internal usage for uploads, generates automaticlly).

---

## 📜 Version History & Changelog

### v2.5.3 (Current) - *The "Cleanup" Update*
- **Refactoring**:
  - Moved legacy install scripts to `scripts/`.
  - Created unified `install.py` entry point.
  - Deep cleaned root directory (moved `config.json` to `.backups/old`).
- **Documentation**:
  - Split `README.md` (Users) and `DEVELOPER.md` (Devs/AI).
  - Strict Emoji ban in terminal/logs.
- **Bug Fixes**:
  - Fixed race conditions in config saving via `utils/config.py`.

### v2.5.2 - *Automation & Community*
- Added `cogs/events.py` for scheduling.
- Added `cogs/automation.py` for AI MOTD and Chat Triggers.
- Implemented Context-Aware Triggers (Log scanning).

### v2.5.0 - *Advanced Features*
- **Stats**: NBT Parsing (`nbtlib`) for offline player data.
- **Info**: `psutil` integration for real hardware monitoring.
- **Backups**: `pyonesend` integration for cloud zip sharing.
- **Economy**: Added "Word Hunt" and Balance system.

### v2.0.0 - *The Rewrite*
- Shifted to `discord.py` 2.0+ (Slash Commands).
- Introduced `cogs` architecture.
- Added `aiofiles` for non-blocking log tailing.

### v1.0.0 - *Legacy*
- Basic start/stop script.
- Single file monolith.

---

## 🧑‍💻 Developer Guide

### Adding a New Cog
1. Create `cogs/my_feature.py`.
2. Class inherits `commands.Cog`.
3. Add `setup(bot)` function.
   ```python
   async def setup(bot):
       await bot.add_cog(MyFeature(bot))
   ```
4. Bot loads it automatically at startup.

### Running Tests
- **Dry Run**: `python bot.py --dry-run`
  - Simulates logic without touching files/Discord.
- **Test Mode**: `python bot.py --test`
  - Runs with a Mock Server (no Java required).
