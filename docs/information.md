# MC-Bot — Complete Developer Reference

_(Note: The `DEVELOPER.md` file has been merged into this document)._

**Version:** `v3.0.0-dev`  
**Last Updated:** 2026-05-22  
**Author:** slogiker - Daniel Pliberšek  
**License:** MIT

> This document is the single source of truth for architecture, commands, configuration, version history, bugs, todos, and internal notes. It is intentionally verbose and designed to be fed directly to LLMs or read by developers onboarding to the project.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [Architecture Deep Dive](#3-architecture-deep-dive)
4. [Configuration System](#4-configuration-system)
5. [All Discord Commands](#5-all-discord-commands)
6. [All Terminal / Docker Commands](#6-all-terminal--docker-commands)
7. [Installation & Setup](#7-installation--setup)
8. [Cog Reference](#8-cog-reference)
9. [Source Module Reference](#9-source-module-reference)
10. [Known Bugs & Technical Debt](#10-known-bugs--technical-debt)
11. [Version History & Recent Changes](#11-version-history--recent-changes)
12. [Completed Features](#12-completed-features)
13. [TODO — Active Roadmap](#13-todo--active-roadmap)
14. [Development Workflow & Rules](#14-development-workflow--rules)
15. [Deployment Notes](#15-deployment-notes)

---

## 1. Project Overview

MC-Bot is a self-hosted Discord bot that manages a Minecraft Java server running inside Docker. The bot runs as a Python process inside a Docker container alongside the Minecraft server process (managed via `tmux`) and an optional Playit.gg agent (also managed via `tmux`).

**Core stack:**

- Python 3.11 + discord.py 2.x
- Docker + Docker Compose
- Java 21 (OpenJDK headless, inside the same container)
- tmux (process management for the MC server inside the container)
- RCON (bot→server command bridge)
- Playit.gg (optional NAT traversal / public IP tunnel) running via `apt` inside the container

**Design philosophy:**

- Everything runs in one Docker container (bot + MC process via `tmux` + playit via `tmux`) to keep networking simple — RCON connects to `127.0.0.1` and is never exposed to the host.
- Config is split: `bot_config.json` is machine state (channel IDs, player lists, session data), `user_config.json` is human preferences (RAM, schedules, role permissions).
- **Atomic Config System:** Uses `FileLock` + Context Managers for race-condition-free Read-Modify-Write cycles.
- Log streaming is centralized through `LogDispatcher` — one `tail -F` subprocess fans out to all subscribers via `asyncio.Queue`.
- **Command Isolation:** The bot enforces slash commands to only be run in the designated `#command` channel (with ephemeral warnings for violations) to keep the main chat clean.
- **Dynamic Presence:** The Bot's status natively reflects the RCON status (verified via handshake). It stays in DND/Idle until RCON responds.

---

## 2. Repository Structure

```
mc-bot/
├── bot.py                      # Main entry point. Bot class, startup, shutdown
├── Dockerfile                  # Python 3.11 + Java 21 + tmux + playit agent
├── Dockerfile.test             # Test-only Docker image (pytest, no runtime deps)
├── docker-compose.yml          # mc-bot service
├── docker-compose.test.yml     # Isolated test-runner compose file
├── Makefile                    # make test / test-verbose / test-single / up / down
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── .gitignore
├── .dockerignore
├── LICENSE                     # MIT
│
├── cogs/                       # Discord command modules (loaded dynamically)
│   ├── __init__.py
│   ├── admin.py                # /sync, /reload_config, /whitelist_add
│   ├── automation.py           # /trigger_* — chat triggers
│   ├── backup.py               # /backup, /backup_list, /backup_download + scheduled
│   ├── console.py              # /logs (redesigned v3), /cmd
│   ├── control_panel.py        # Sticky interactive control panel embed
│   ├── _economy.py             # [DISABLED] Economy module
│   ├── events.py               # /event_create, /event_list, /event_delete
│   ├── help.py                 # /help — dynamic, permission-filtered
│   ├── info.py                 # /status, /version, /seed, /info, /players (v3 fallback)
│   ├── link.py                 # /link, /unlink, /unlink_admin, /verify (v3)
│   ├── management.py           # /start, /stop, /kill (v3), /restart, /bot_restart
│   ├── mods.py                 # /mods (v3 platform-aware), /mod_search
│   ├── players.py              # /players (GUI selection for management)
│   ├── player_tracker.py       # Background player tracking
│   ├── playit.py               # /ip — Playit.gg address fetcher
│   ├── settings.py             # Interactive /settings
│   ├── setup.py                # /setup — install wizard
│   ├── stats.py                # /stats — player statistics
│   └── tasks.py                # Background tasks (v3 RCON presence task)
│
├── src/                        # Core logic (non-Discord)
│   ├── __init__.py
│   ├── auto_setup.py           # Standalone fallback: creates Discord roles/channels via API
│   ├── backup_manager.py       # Zip world, pyonesend, retention cleanup
│   ├── config.py               # Singleton Config class, JSON r/w with FileLock
│   ├── join_guard.py           # UUID-based session tracking (v3), /verify logic
│   ├── log_dispatcher.py       # Singleton — tail -F fan-out
│   ├── log_watcher.py          # Subscribes to LogDispatcher, parses auth lines
│   ├── logger.py               # Daily rotation, monthly zip, custom format
│   ├── mc_installer.py         # Platform-aware JAR downloader (v3 fresh fetch)
│   ├── mc_link_manager.py      # CRUD for Discord↔MC linkage (data/mc_links.json)
│   ├── mc_manager.py           # Helper: get_server_properties() reader
│   ├── mod_updater.py          # Modrinth plugin/mod fetcher
│   ├── mojang.py               # Mojang API lookup — hardened v3 (fail-closed)
│   ├── server_info_manager.py  # Manages #server-information channel embed
│   ├── server_interface.py     # Base class with emergency_stop (v3)
│   ├── server_mock.py          # MockServerManager for --simulate mode
│   ├── server_tmux.py          # TmuxServerManager (real server control)
│   ├── setup_helper.py         # Creates Discord roles/channels/categories
│   ├── setup_views.py          # Multi-step setup form UI (v3 vanilla support)
│   ├── utils.py                # rcon_cmd(), has_role(), get_server_mod_folder() (v3)
│   ├── version_fetcher.py      # Cached API calls with force_fresh (v3)
│   └── views.py                # Shared generic UI views
│
├── data/                       # Persistent config (mounted as volume)
│   ├── bot_config.json         # Machine state
│   ├── user_config.json        # User preferences
│   ├── mc_links.json           # Discord↔MC account linkage DB
│   └── playit_secret.key       # Playit agent authentication key
│
├── docs/                       # Documentation
│   ├── information.md          # (this file)
│   ├── commands.md             # Complete command cheatsheet
│   ├── error_codes.md          # Error lookup table
│   └── implementations/        # Internal design specs
│
├── tests/                      # Unit & Integration Tests
│   ├── infra/                  # Test infrastructure
│   ├── conftest.py             # Shared fixtures
│   └── test_*.py               # Pytest test files
│
├── install/                    # Installation helpers
│   ├── install.sh              # Linux/WSL installer
│   ├── install.bat             # Windows setup guide (re-architected v3)
│   ├── install.ps1             # NEW: WSL2 architecture installer for Windows (v3)
│   ├── .env.example            # Environment template
│   ├── simulate.py             # Launches bot with --simulate flag
│   └── update.py               # update script
│
├── mc-server/                  # Minecraft server files
│   ├── server.jar
│   ├── server.properties
│   ├── world/
│   ├── logs/
│   └── ...
│
├── backups/                    # World backups
│   ├── auto/                   # Scheduled backups
│   └── custom/                 # Manual backups
│
└── logs/                       # Application logs
    ├── bot.log                 # Current bot log
    ├── playit.log              # Agent tunnel logs
    ├── install-log.txt         # Installer history
    └── YYYY-MM/                # Rotated logs
```

---

## 3. Architecture Deep Dive

### 3.1 Bot Startup Sequence

```
bot.py main()
  └─ MinecraftBot.__init__()
       ├─ config.set_simulation_mode(is_simulation)
       ├─ TmuxServerManager() or MockServerManager()
       ├─ JoinGuard(bot)               — login interceptor (UUID-based sessions v3)
       ├─ LogWatcher(bot)              — subscribes to LogDispatcher
       ├─ add_listener(on_minecraft_player_login)
       └─ setup_hook()
            ├─ Load all cogs from ./cogs/*.py
            └─ (sync happens in on_ready, not here)

  └─ on_ready()
       ├─ Resolve guild (GUILD_ID or first guild)
       ├─ SetupHelper.ensure_setup(guild)
       │    ├─ Create/find roles: MC Admin, MC Player
       │    ├─ Create/find category: Minecraft Server
       │    └─ Create/find channels: command, log, debug
       ├─ config.update_dynamic_config(updates)
       ├─ tree.copy_global_to(guild) + tree.sync(guild)
       ├─ update_presence_loop()        — NEW v3 (verified RCON status handshake)
       └─ If server is_running() → log_dispatcher.start() + log_watcher.start()
```

### 3.2 Log Dispatcher

**Solution:** `LogDispatcher` is a singleton that:

1. Spawns exactly ONE `tail -F mc-server/logs/latest.log` subprocess (high-performance fan-out).
2. Reads stdout line-by-line.
3. Broadcasts each line to all subscriber `asyncio.Queue` instances.

**Subscribers currently:**

- `console.py` — streams to Discord log channel (redesigned with interactive filters v3)
- `automation.py` — scans for trigger phrases
- `log_watcher.py` — scans for login events (v3 UUID session handling)

### 3.3 Server Manager Hierarchy (v3 Update)

```
ServerInterface (ABC)           src/server_interface.py
  ├─ TmuxServerManager          src/server_tmux.py      (added emergency_stop)
  └─ MockServerManager          src/server_mock.py      (simulation mode)
```

**Emergency Stop (/kill):** If a graceful RCON stop hangs, `emergency_stop()` forcefully terminates the tmux session (`kill-session`).

### 3.4 Config System (v3 Update)

Tracks platform and version reliably:
- `config.INSTALLED_PLATFORM`: (vanilla, paper, fabric, forge)
- `config.INSTALLED_VERSION`: (e.g. "1.21.4")
Used for intelligent folder detection and command behavior.

### 3.5 RCON Communication (v3 Hardening)

`rcon_cmd(cmd)` call sites now handle malformed responses (tuples vs strings) defensively.
**Handshake:** Bot presence stays "Starting" until the first successful RCON handshake.

---

## 4. Configuration System

### 4.2 `data/bot_config.json` — Machine State

```json
{
  "server_directory": "/app/mc-server",
  "installed_platform": "paper",
  "installed_version": "1.21.4",
  "verified_sessions": {},
  "grace_periods": {},
  "online_players": [],
  "owner_id": null,
  "control_panel_message_id": null
}
```

---

## 5. All Discord Commands

### Server Control

| Command          | Permission    | Description                                                                                  |
| ---------------- | ------------- | -------------------------------------------------------------------------------------------- |
| `/start`         | `start`       | Start the Minecraft server.                                                                  |
| `/stop`          | `stop`        | Graceful stop via RCON. Waits 5s, kills if needed.                                           |
| `/kill`          | `stop`        | **NEW v3:** Force-kill tmux session (emergency hard-stop).                                   |
| `/restart`       | `restart`     | Stop + start with delay.                                                                     |
| `/control`       | `control`     | Sticky button panel.                                                                         |

### Server Information (v3 Updates)

| Command                  | Permission    | Description                                                                                          |
| ------------------------ | ------------- | ---------------------------------------------------------------------------------------------------- |
| `/status`                | `status`      | Online/Offline + player count (v3 formatted names).                                                  |
| `/players`               | `players`     | List online players. **v3:** Falls back to log memory if RCON is down.                              |
| `/logs`                  | `logs`        | **RE-DESIGNED v3:** Interactive filters (Chat, Joins, Errors, Raw).                                  |
| `/mods`                  | `mods`        | **v3:** Platform-aware (checks `mods/` or `plugins/`). Skips for Vanilla.                            |

### Security & Linking (v3)

| Command                           | Permission      | Description                                                                       |
| --------------------------------- | --------------- | --------------------------------------------------------------------------------- |
| `/link <username>`                | open            | Link Discord account. Hardened Mojang premium detection.                          |
| `/verify <code>`                  | open            | **NEW v3:** Production-ready login verification using kick screen code.           |
| `/unlink`                         | open            | Remove link.                                                                      |

---

## 7. Installation & Setup

### 7.1 Linux / Standard WSL

```bash
git clone https://github.com/slogiker/mc-bot.git
cd mc-bot
chmod +x install/install.sh
./install/install.sh
```

### 7.2 Windows (Experimental - v3 Architecture)

`install/install.bat` → `install/install.ps1`:
1. Checks for WSL2 and Virtual Machine Platform.
2. Automatically installs/enables WSL and Ubuntu if missing.
3. Launches the Linux `install.sh` **inside** the Ubuntu distro.
4. **Result:** 100% Docker/tmux compatibility for Windows users.

---

## 8. Cog Reference

### `cogs/console.py` (v3 Redesign)

Now uses `LogsView` (discord.ui.View):
- `[Default (Filtered)]`: Joins, Leaves, Deaths, Chat, Errors.
- `[Chat Only]`: Strict regex match for `<player> msg`.
- `[Errors/Warnings]`: Case-insensitive grep for ERROR/WARN.
- `[Joins/Leaves]`: Connection/Disconnection events.
- `[Raw/All]`: Every log line.
Automatically truncates from top to fit Discord's 2000-char limit.

---

## 9. Source Module Reference

### `src/join_guard.py` (v3 Security Hardening)

Overhauled to be **mascan-proof**:
1. **UUID Sessions:** Grace periods are tied to specific MC UUIDs, not usernames.
2. **Brute-Force:** `/verify` allows 3 attempts before challenge invalidation.
3. **Fail-Closed:** Mojang API failures now block login by default (safety first).
4. **No Sleep:** Removed the 1s delay before kicks to mitigate griefing races.

### `src/mc_installer.py` (v3 Freshness)

`get_latest_version()` now forces a cache bypass in `VersionFetcher`. This ensures that when a user selects "latest" during setup, it queries the API at that exact moment rather than using a 1-hour old cache.

---

## 11. Version History & Recent Changes

### v3.0.0-dev — Security & Reliability Overhaul (2026-05-22)

**Major Changes:**
- **UUID Verification:** Overhauled JoinGuard to use UUID-based session tracking, preventing impersonation via name-spoofing in offline mode.
- **Interactive Logs:** Redesigned `/logs` with categorized filtering buttons and RCON noise reduction.
- **Emergency Controls:** Added `/kill` command and underlying `emergency_stop` method for hard-killing the Minecraft process.
- **Native Vanilla Support:** Setup wizard and `/mods` command now intelligently detect Vanilla platforms and skip mods/plugins logic.
- **RCON Handshake:** Bot presence now accurately reflects server readiness by waiting for a successful RCON command before going "Online".
- **Windows Architecture:** Re-architected Windows installation to run inside a dedicated WSL2 Ubuntu environment for maximum stability.

---

## 12. Completed Features (v3)

- ✅ **Emergency Stop (/kill)** — Force-kill tmux session.
- ✅ **Interactive /logs** — Categorized filtering (Chat, Errors, etc.).
- ✅ **UUID Sessions** — Secure offline-mode protection.
- ✅ **Vanilla Detection** — Automated mods/plugins skipping.
- ✅ **Fresh Setup** — "Latest" version always queries API at install time.
- ✅ **RCON Presence** — Online status verified via real handshake.
- ✅ **WSL2 Installer** — Production-ready Windows setup.

---

## AI Agent Prompt Instructions

> **System Instruction:** Maintain this file as the canonical source of truth. It must remain verbose and structural. At each architectural change, update the relevant deep-dive sections and version history. DO NOT truncate or "clean" the structure unless explicitly asked.
