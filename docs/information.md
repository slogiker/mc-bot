# MC-Bot — Complete Developer Reference

**Version:** `v3.0.0-dev`  
**Last Updated:** 2026-05-22  
**Author:** slogiker - Daniel Pliberšek  
**License:** MIT

> This document is the single source of truth for architecture, commands, configuration, version history, bugs, and development standards.

---

## 1. Project Overview

MC-Bot is a self-hosted Discord bot designed to manage a Minecraft Java server with zero friction. Everything runs inside a single Docker container, including the bot, the Minecraft process (via `tmux`), and an optional public IP tunnel (via `playit`).

### Core Philosophy
- **Containerized Simplicity:** One container, one volume set. No complex networking.
- **RCON Control:** All server interactions happen over local RCON.
- **Log Streaming:** Real-time console logs are streamed to Discord via a high-performance `tail -F` fan-out system.
- **Resilience:** Built-in crash detection, RCON fallbacks, and emergency hard-kill commands.
- **Security:** Strict role-based permissions and an offline-mode impersonation protection system.

---

## 2. Repository Structure

```
mc-bot/
├── bot.py                  # Main entry point & Discord client
├── Dockerfile              # Python 3.11 + Java 21 + tmux
├── docker-compose.yml      # Service definition with PUID/PGID support
├── requirements.txt        # Pinned dependencies
├── Makefile                # Shortcuts (make test, make clean)
│
├── cogs/                   # Discord Command Modules
│   ├── admin.py            # /sync, /reload_config
│   ├── automation.py       # Chat triggers & MOTD
│   ├── backup.py           # /backup & direct downloads
│   ├── console.py          # /logs (filtered console streaming)
│   ├── info.py             # /status, /players, /info, /seed
│   ├── management.py       # /start, /stop, /kill, /restart
│   ├── link.py             # /link (Account linking)
│   ├── mods.py             # /mod_search (Modrinth integration)
│   ├── stats.py            # /stats (NBT achievement parsing)
│   └── tasks.py            # Crash checker & background presence
│
├── src/                    # Core Logic
│   ├── config.py           # Singleton Atomic Config (FileLock)
│   ├── join_guard.py       # Login security & DM challenges
│   ├── log_dispatcher.py   # Real-time log multiplexer
│   ├── mc_installer.py     # Platform-aware server downloader
│   ├── server_tmux.py      # Tmux process manager
│   ├── version_fetcher.py  # Cached API version resolver
│   └── utils.py            # rcon_cmd, folder detection, permissions
│
├── data/                   # Persistent config (bot_config.json, user_config.json)
├── mc-server/              # Minecraft server files & worlds
├── backups/                # Automated and manual world backups
└── logs/                   # Bot and installation logs
```

---

## 3. Architecture Deep Dive

### 3.1 Process Management (`server_tmux.py`)
The Minecraft server runs in a `tmux` session named `minecraft`. This allows developers to attach to the console manually if needed, while providing the bot a clean way to send commands via `send-keys`.

### 3.2 Communication (RCON)
The bot uses `aiomcrcon` to communicate with the server.
- **Fallback Logic:** If RCON is unavailable (server hanging), the bot falls back to **Log-Watcher memory** to show who was online and provides the `/kill` command to terminate the tmux session.

### 3.3 Log Dispatcher (`log_dispatcher.py`)
A single `tail -F` process reads `latest.log`. Lines are pushed into an `asyncio.Queue` and broadcast to:
1. `LogWatcher`: For join/leave detection and security checks.
2. `ConsoleCog`: For filtered log streaming to Discord.
3. `AutomationCog`: For chat triggers.

---

## 4. Configuration System

### 4.1 Atomic Operations
All configuration changes use `FileLock`.
- `update_bot_config()`: For machine-managed state (channel IDs, player lists).
- `update_user_config()`: For human-managed state (RAM, schedules, permissions).

### 4.2 Permission Roles
Permissions are defined in `user_config.json` by command name.
- **Owner:** Full access to all commands.
- **Admin:** Access to management, core settings, and console.
- **Player:** Access to basic info and stats.

---

## 5. Security: JoinGuard

Protects cracked/offline-mode servers from impersonation.
1. **Detection:** LogWatcher detects a connection.
2. **Decision:**
   - Premium Account? → Allow.
   - Linked Cracked Account? → DM 4-digit code challenge.
   - Unlinked? → Kick with instruction to /link.
3. **Grace Period:** 30-minute window after disconnect where no challenge is required.

---

## 6. Installation Flow

### 6.1 Linux
The `install/install.sh` script automates dependency checks (Docker, Git), environment creation (`.env`), and container startup.

### 6.2 Windows (Experimental)
Windows installation is supported via **WSL2**. 
- `install/install.bat` guides the user through WSL setup.
- The real installer runs inside an Ubuntu WSL environment to ensure 100% compatibility with Docker and tmux.

---

## 7. Version History (Recent)

### v3.0.0-dev (2026-05-22)
- **RCON Reliability:** Added `/kill` command and log-based player list fallbacks.
- **Vanilla Support:** Setup wizard and `/mods` command now natively support Vanilla servers (skips mod steps).
- **Setup UX:** Resolved "latest" version staleness by forcing a fresh fetch at install time.
- **Presence Logic:** Bot status now stays "Starting" until the first successful RCON handshake.
- **Filtered Logs:** `/logs` command redesigned with interactive buttons (Chat, Errors, Joins, etc.).
- **Atomic Persistence:** Config now tracks `INSTALLED_PLATFORM` and `INSTALLED_VERSION` reliably.

### v2.9.0
- Replaced loose JSON R/W with context-managed atomic operations.
- Organization: Moved internal docs and test infra to dedicated subdirectories.

---

## 8. Development Rules
- **Atomic Config:** Always use `with config.update_...` when modifying settings.
- **Defer Interactions:** Minecraft operations take time. Always `interaction.response.defer()` early.
- **RCON Sanitation:** Sanitize all RCON inputs to prevent command injection.
- **Documentation:** Every feature must be documented in `information.md`.

---

## AI Agent Prompt Instructions

> **System Instruction:** Maintain this file as the canonical source of truth. At each architectural change, update the structure, version history, and relevant deep-dive sections. This document must always be accurate enough to allow an LLM to recreate the project's logic.
