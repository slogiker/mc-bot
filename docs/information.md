# MC-Bot — Complete Developer Reference

_(Note: The `DEVELOPER.md` file has been merged into this document)._

**Version:** `v2.7.2`  
**Last Updated:** March 2026  
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
- Config is split: `bot_config.json` is machine state (channel IDs, player lists), `user_config.json` is human preferences (RAM, schedules, role permissions).
- Log streaming is centralized through `LogDispatcher` — one `docker logs -f` subprocess fans out to all subscribers via `asyncio.Queue`.
- **Command Isolation:** The bot enforces slash commands to only be run in the designated `#command` channel (with ephemeral warnings for violations) to keep the main chat clean.
- **Dynamic Presence:** The Bot's status natively reflects the Docker process (Online, Idle/Starting, Offline/DND).

---

## 2. Repository Structure

```
mc-bot/
├── bot.py                      # Main entry point. Bot class, startup, shutdown
├── Dockerfile                  # Python 3.11 + Java 21 + tmux + playit agent
├── docker-compose.yml          # mc-bot service
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── .gitignore
├── .dockerignore
├── LICENSE                     # MIT
│
├── cogs/                       # Discord command modules (loaded dynamically)
│   ├── __init__.py
│   ├── admin.py                # /sync, /backup_now, /logs, /whitelist_add
│   ├── automation.py           # /motd, /trigger_* — MOTD + chat triggers
│   ├── backup.py               # /backup, /backup_list, /backup_download + scheduled
│   ├── console.py              # Live log tailing → Discord, /cmd
│   ├── control_panel.py        # Sticky interactive control panel embed
│   ├── economy.py.disabled     # [DISABLED] /balance, /pay, /economy_set + Word Hunt
│   ├── events.py               # /event_create, /event_list, /event_delete
│   ├── help.py                 # /help
│   ├── info.py                 # /status, /version, /seed, /info
│   ├── management.py           # /start, /stop, /restart, /control, /bot_restart
│   ├── mods.py                 # /mods
│   ├── players.py              # /players
│   ├── playit.py               # /ip — Playit.gg address fetcher via REST API
│   ├── settings.py             # Server settings
│   ├── setup.py                # /setup — triggers the install wizard
│   ├── stats.py                # /stats — NBT + Mojang API player statistics
│   └── tasks.py                # Background: crash check, log monitor, daily backup
│
├── src/                        # Core logic (non-Discord)
│   ├── __init__.py
│   ├── auto_setup.py           # Standalone fallback: creates Discord roles/channels via API
│   ├── backup_manager.py       # Zip world, upload via pyonesend, retention cleanup
│   ├── config.py               # Singleton Config class, JSON r/w with FileLock
│   ├── log_dispatcher.py       # Singleton — tail -F fan-out
│   ├── logger.py               # Daily rotation, monthly zip, custom format
│   ├── mc_installer.py         # Download Paper/Vanilla/Fabric JARs, configure props
│   ├── mc_manager.py           # Helper: get_server_properties() reader
│   ├── mod_updater.py          # Modrinth plugin/mod fetcher
│   ├── server_info_manager.py  # Manages #server-information channel embed
│   ├── server_interface.py     # Abstract base class ServerInterface
│   ├── server_mock.py          # MockServerManager for --simulate mode
│   ├── server_tmux.py          # TmuxServerManager (real server control)
│   ├── setup_helper.py         # Creates Discord roles/channels/categories
│   ├── setup_views.py          # Multi-step setup form UI (discord.ui)
│   ├── utils.py                # rcon_cmd(), has_role(), send_debug(), get_uuid()
│   ├── version_fetcher.py      # Cached API calls for Paper/Vanilla/Fabric versions
│   └── views.py                # Shared generic UI views
│
├── data/                       # Persistent config (mounted as volume)
│   ├── bot_config.json         # Machine state (channel IDs, guild ID, economy, events)
│   └── user_config.json        # User preferences (RAM, schedule, role permissions)
│   └── playit_secret.key       # Auto-generated Playit agent authentication key
│
├── install/                    # Installation helpers
│   ├── install.sh              # Linux/WSL installer (Docker + .env + compose up)
│   ├── install.bat             # Windows installer (WSL2 + Docker Engine, resumable)
│   ├── wsl_docker_setup.sh     # Called by install.bat — installs Docker Engine inside WSL
│   ├── simulate.py             # Launches bot with --simulate flag for local testing
│   └── update.py               # Dev rebuild script: updates from git checks and rebuilds docker
│
├── docs/                       # Documentation
│   ├── information.md          # (this file — comprehensive version + roadmap + commands)
│
├── mc-server/                  # Minecraft server files (gitignored, Docker volume)
│   ├── server.jar
│   ├── server.properties
│   ├── eula.txt
│   ├── world/
│   ├── logs/
│   └── ...
│
├── backups/                    # World backups (gitignored, Docker volume)
│   ├── auto/                   # Scheduled backups (7-day retention)
│   └── custom/                 # Manual backups (never auto-deleted)
│
└── logs/                       # Bot logs (gitignored, Docker volume)
    ├── bot.log                 # Current log file
    └── YYYY-MM/                # Rotated logs (auto-zipped monthly)
```

---

## 3. Architecture Deep Dive

### 3.1 Bot Startup Sequence

```
bot.py main()
  └─ MinecraftBot.__init__()
       ├─ config.set_simulation_mode(is_simulation)
       ├─ TmuxServerManager() or MockServerManager()
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
       └─ Set bot presence (Online/Offline based on server state)
```

### 3.2 Log Dispatcher

**Problem solved:** Multiple cogs (console, automation, economy) all need the Minecraft server logs in real-time. Naively, each cog would spawn its own `docker logs -f` process, wasting resources.

**Solution:** `LogDispatcher` is a singleton that:

1. Spawns exactly ONE `docker logs -f --tail 0 mc-bot` subprocess.
2. Reads stdout line-by-line.
3. Broadcasts each line to all subscriber `asyncio.Queue` instances.

```python
# Any cog that needs logs:
from src.log_dispatcher import log_dispatcher

async def cog_load(self):
    self.log_queue = log_dispatcher.subscribe()
    await log_dispatcher.start()   # idempotent — only starts once

# Then in a task:
line = await asyncio.wait_for(self.log_queue.get(), timeout=1.0)
```

**Subscribers currently:**

- `console.py` — streams to Discord log channel
- `automation.py` — scans for trigger phrases
- `economy.py` — monitors for Word Hunt winners

### 3.3 Server Manager Hierarchy

```
ServerInterface (ABC)           src/server_interface.py
  ├─ TmuxServerManager          src/server_tmux.py      (production)
  └─ MockServerManager          src/server_mock.py      (--simulate mode)
```

`TmuxServerManager` manages a named tmux session (`minecraft`) inside the Docker container. The bot sends commands to the MC process by running `tmux send-keys`. Server start/stop persists intentional-stop state to `mc-server/bot_state.json` to distinguish crashes from intentional stops.

`MockServerManager` mimics all operations with fake delays and no file I/O. Useful for testing Discord commands without running a real server.

### 3.4 Permission System

Permissions are role-name based in `user_config.json`:

```json
{
  "permissions": {
    "Owner": ["cmd", "sync", "start", "stop", ...],
    "Admin": ["start", "stop", "restart", ...],
    "Player": ["status", "balance", "pay", ...],
    "@everyone": ["status", "players", "help"]
  }
}
```

At runtime, `config.resolve_role_permissions(guild)` maps role names → IDs into `config.ROLES`. The `has_role(cmd_name)` decorator in `utils.py` checks this map first (by ID), then falls back to checking role names directly against `user_config.permissions`.

### 3.5 Control Panel

`cogs/control_panel.py` maintains a single sticky embed in the `#command` channel. A `tasks.loop(minutes=2)` task refreshes it. The embed has a persistent `ControlPanelView` with buttons: Start, Stop, Restart, Status. The view is re-registered on every bot start so buttons survive restarts (`bot.add_view(ControlPanelView(bot))` in `on_ready`).

### 3.6 Setup Wizard Flow

`/setup` → `cogs/setup.py` → `src/setup_views.py (SetupView)`:

```
Step 1: Platform     (Paper / Vanilla / Fabric)
Step 2: Version      (dropdown from Modrinth API or fallback list)
Step 3: Difficulty
Step 4: Seed         (optional custom or random)
Step 5: Max Players
Step 6: Advanced     (RAM, view distance, whitelist, online mode)
Step 7: Plugins/Mods (Modrinth project slugs to auto-download)
Step 8: Confirm → Install

Install flow:
  1. SetupHelper.ensure_setup()     → Discord roles & channels
  2. mc_installer.download_server() → Download JAR
  3. mc_installer.accept_eula()     → Write eula.txt
  4. mc_installer.configure_server_properties()
  5. ModUpdater                     → Fetches specific plugins, updates existing
  6. server.start()
  7. ServerInfoManager.update_info()
```

---

## 4. Configuration System

### 4.1 Environment Variables (`.env`)

| Variable            | Required | Description                                 |
| ------------------- | -------- | ------------------------------------------- |
| `BOT_TOKEN`         | ✅       | Discord bot token                           |
| `RCON_PASSWORD`     | ✅       | RCON password (auto-generated by installer) |
| `PLAYIT_SECRET_KEY` | ❌       | Optional. Auto-generated via claim flow or read from `data/playit_secret.key` |

### 4.2 `data/bot_config.json` — Machine State

Managed by the bot. Do not edit manually while the bot is running.

```json
{
  "server_directory": "/app/mc-server",
  "guild_id": null,
  "command_channel_id": null,
  "log_channel_id": null,
  "debug_channel_id": null,
  "info_channel_id": null,
  "backup_channel_id": null,
  "owner_id": null,
  "admin_role_id": null,
  "player_role_id": null,
  "spawn_x": null,
  "spawn_y": null,
  "spawn_z": null,
  "online_players": [],
  "economy": {},
  "events": [],
  "mappings": {},
  "last_auto_backup": "",
  "installed_version": ""
}
```

### 4.3 `data/user_config.json` — User Preferences

Edit this freely between restarts.

```json
{
  "java_ram_min": "2G",
  "java_ram_max": "4G",
  "backup_time": "03:00",
  "backup_keep_days": 7,
  "restart_time": "04:00",
  "timezone": "Europe/Ljubljana",
  "permissions": {
    "Owner":     ["cmd", "sync", "start", "stop", "restart", ...],
    "Admin":     ["start", "stop", "restart", ...],
    "Player":    ["status", "balance", "pay", ...],
    "@everyone": ["status", "players", "help"]
  },
  "log_blacklist": [],
  "triggers": {}
}
```

**Validation rules** (enforced on load by `validate_user_config()`):

- `java_ram_min` / `java_ram_max`: must match `^\d+[MG]$`, min ≤ max
- `backup_time` / `restart_time`: must be `HH:MM` format
- `backup_keep_days`: integer 1–365
- `timezone`: any string (validated by pytz at use)
- `permissions`: must be a dict

### 4.4 Config Class — Key Methods

```python
config.load_bot_config()       → dict   (thread-safe FileLock read)
config.save_bot_config(data)   → None   (thread-safe FileLock write)
config.load_user_config()      → dict
config.save_user_config(data)  → None
config.update_dynamic_config(updates: dict)   → updates memory attrs
config.resolve_role_permissions(guild)         → populates config.ROLES
config.set_simulation_mode(bool)               → sets dry_run flag
config.get(key, default=None)                  → safe attribute getter
```

### 4.5 Config Attributes at Runtime

| Attribute                      | Source               | Description      |
| ------------------------------ | -------------------- | ---------------- |
| `config.TOKEN`                 | env                  | Bot token        |
| `config.RCON_PASSWORD`         | env                  | RCON password    |
| `config.RCON_HOST`             | hardcoded            | `127.0.0.1`      |
| `config.RCON_PORT`             | hardcoded            | `25575`          |
| `config.SERVER_DIR`            | bot_config           | `/app/mc-server` |
| `config.GUILD_ID`              | bot_config           | Discord guild ID |
| `config.COMMAND_CHANNEL_ID`    | bot_config           |                  |
| `config.LOG_CHANNEL_ID`        | bot_config           |                  |
| `config.DEBUG_CHANNEL_ID`      | bot_config           |                  |
| `config.OWNER_ID`              | bot_config           | Discord user ID  |
| `config.JAVA_XMX`              | user_config          | Max JVM heap     |
| `config.JAVA_XMS`              | user_config          | Min JVM heap     |
| `config.BACKUP_TIME`           | user_config          | `HH:MM`          |
| `config.BACKUP_RETENTION_DAYS` | user_config          | Integer          |
| `config.TIMEZONE`              | user_config / ip-api | pytz string      |
| `config.ROLE_PERMISSIONS`      | user_config          | Dict name→cmds   |
| `config.ROLES`                 | runtime              | Dict ID→cmds     |
| `config.CRASH_CHECK_INTERVAL`  | hardcoded            | 30 (seconds)     |
| `config.WORLD_FOLDER`          | hardcoded            | `world`          |

---

## 5. All Discord Commands

### Server Control

| Command          | Permission    | Description                                                                                  |
| ---------------- | ------------- | -------------------------------------------------------------------------------------------- |
| `/start`         | `start`       | Start the Minecraft server. Cooldown: 30s.                                                   |
| `/stop`          | `stop`        | Graceful stop. Sends `stop` command via RCON, waits 5s, kills tmux if needed. Cooldown: 30s. |
| `/restart`       | `restart`     | Stop + start with `RESTART_DELAY` (5s) gap. Cooldown: 60s.                                   |
| `/control`       | `control`     | Spawns inline ControlView with Start/Stop/Restart/Status buttons.                            |
| `/bot_restart`   | `bot_restart` | `sys.exit(0)` — hot-restarts the bot process utilizing Docker's auto-restart policy.         |
| `/cmd <command>` | owner only    | Execute raw RCON command. Audit-logged to debug channel.                                     |

### Server Information

| Command                  | Permission    | Description                                                                                          |
| ------------------------ | ------------- | ---------------------------------------------------------------------------------------------------- |
| `/status`                | `status`      | Online/Offline + player list embed.                                                                  |
| `/players`               | `players`     | `list` via RCON → formatted embed.                                                                   |
| `/version`               | `version`     | Parses version from `latest.log`.                                                                    |
| `/seed`                  | `seed`        | Reads `level-seed` from `server.properties`, fallback RCON.                                          |
| `/mods`                  | `mods`        | Lists `.jar` files in `mc-server/mods/`.                                                             |
| `/info`                  | `server_info` | Full embed: IP, version, CPU, RAM, Disk, players, spawn. Also updates `#server-information` channel. |
| `/ip`                    | open          | Fetches public Playit.gg address via API using agent-key. Cached in memory.                              |
| `/set_spawn <x> <y> <z>` | `set_spawn`   | Saves spawn coords to `bot_config.json`, updates info channel. Admin only.                           |

### Administration

| Command                     | Permission      | Description                                                                                                             |
| --------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `/setup`                    | server admin    | Full interactive multi-step install wizard. Creates channels, downloads server, fetches plugins, configures everything. |
| `/sync`                     | `sync`          | Re-syncs slash commands to guild.                                                                                       |
| `/settings`                 | `cmd`           | Interactive GUI to modify Bot and Server configurations (RAM, Schedules, Timezone, Permissions)                         |
| `/backup_now [name]`        | `backup_now`    | Triggers immediate backup. Cooldown: 5min.                                                                              |
| `/logs [lines]`             | `logs`          | Shows last N lines from `docker logs`. Sent to log channel.                                                             |
| `/whitelist_add <username>` | `whitelist_add` | RCON `whitelist add` + `whitelist reload`.                                                                              |

### Backup

| Command                       | Permission        | Description                                                                              |
| ----------------------------- | ----------------- | ---------------------------------------------------------------------------------------- |
| `/backup [name]`              | `backup`          | Creates backup in `backups/custom/` if named, else `backups/auto/`. Shows Upload button. |
| `/backup_list`                | `backup_list`     | Lists up to 5 most recent auto + custom backups.                                         |
| `/backup_download <filename>` | `backup_download` | Uploads specific backup via pyonesend, returns download link.                            |

### Economy

> **Note:** The Economy module (commands and Word Hunt) is currently disabled per user request, pending integration with a dynamic Minecraft resource API.

| Command                        | Permission      | Description                              |
| ------------------------------ | --------------- | ---------------------------------------- |
| `/balance [user]`              | `balance`       | _(Disabled)_ Shows coin balance.         |
| `/pay <user> <amount>`         | `pay`           | _(Disabled)_ Transfer coins.             |
| `/economy_set <user> <amount>` | `economy_admin` | _(Disabled)_ Admin override for balance. |

### Events

| Command                                                | Permission     | Description                                                                           |
| ------------------------------------------------------ | -------------- | ------------------------------------------------------------------------------------- |
| `/event_create <name> <time> [description] [mentions]` | `event_manage` | Schedule event. Time format: `YYYY-MM-DD HH:MM`. Auto-reminders at 24h and 1h before. |
| `/event_list`                                          | open           | Shows all upcoming events with Discord timestamps.                                    |
| `/event_delete <index>`                                | `event_manage` | Delete event by list index.                                                           |

### Automation & AI

| Command                           | Permission      | Description                                                       |
| --------------------------------- | --------------- | ----------------------------------------------------------------- |
| `/motd <text>`                    | open            | Sets server MOTD via RCON `setmotd` (requires Essentials plugin). |
| `/trigger_add <phrase> <command>` | `trigger_admin` | Add a keyword→RCON command trigger.                               |
| `/trigger_list`                   | `trigger_list`  | Show all configured triggers.                                     |
| `/trigger_remove <phrase>`        | `trigger_admin` | Remove a trigger.                                                 |
| `/stats [player] [user]`          | `stats`         | Player statistics from NBT files + Mojang API.                    |
| `/help`                           | open            | Dynamic help based on caller's roles.                             |

---

## 6. All Terminal / Docker Commands

### Starting / Stopping

```bash
# Start everything
docker compose up -d

# Start with cache bust (use after code changes)
CACHEBUST=$(date +%s) docker compose up -d --build

# Stop everything
docker compose down

# Stop and remove volumes (WARNING: deletes mc-server data)
docker compose down -v

# Restart only the bot
docker compose restart mc-bot
```

### Viewing Logs

```bash
# Follow bot + MC server logs
docker compose logs -f mc-bot

# Last 50 lines, no follow
docker compose logs --tail=50 mc-bot

# Both services simultaneously
docker compose logs -f
```

### Debugging

```bash
# Open shell inside running container
docker exec -it mc-bot /bin/bash

# Attach to Minecraft tmux session
docker exec -it mc-bot tmux attach -t minecraft

# Attach to Playit tmux session
docker exec -it mc-bot tmux attach -t playit

# Check resource usage
docker stats

# Check container status
docker compose ps

# Force rebuild from scratch (clears all caches)
docker buildx prune -af
docker compose build --no-cache
docker compose up -d
```

### Updates

```bash
# Pull latest code and rebuild automatically (ignoring cache if behind)
python install/update.py
```

### Simulation / Testing

```bash
# Run bot in ghost mode (no real server, no file writes)
python install/simulate.py

# Direct simulate flag
python bot.py --simulate
```

### WSL-Specific (Windows)

```bash
# Run any docker command through WSL from PowerShell/CMD
wsl -d MCBot -u mc-bot -- docker compose logs -f mc-bot
wsl -d MCBot -u mc-bot -- docker compose down
wsl -d MCBot -u mc-bot -- docker compose up -d --build
wsl -d MCBot                   # Open interactive WSL shell
```

---

## 7. Installation & Setup

### 7.1 Linux / macOS / Standard WSL

```bash
git clone https://github.com/slogiker/mc-bot.git
cd mc-bot
chmod +x install/install.sh
./install/install.sh
```

The script:

1. Checks if an installation already exists (prompts Reconfigure, Update Code, or Cancel)
2. Checks/installs Docker and Git
3. Prompts for `BOT_TOKEN`, optional Playit setup (Yes/No flow)
4. Auto-generates `RCON_PASSWORD`
5. Writes `.env`
6. Creates `mc-server/`, `backups/`, `logs/` directories
7. Runs `docker compose up -d --build`

After startup, run `/setup` in Discord to create channels and install the Minecraft server.

### 7.2 Windows (install.bat)

`install/install.bat` is a fully automated 8-step installer that handles everything from scratch:

| Step | What Happens                                                                                                                         |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 1    | Admin elevation check. Validates Windows build ≥ 19041, virtualization enabled, ≥5GB disk. 3× YES confirmation if already installed. |
| 2    | Detects Docker Desktop → uses it if found and running. Otherwise offers choice: Docker Desktop download link OR WSL + Docker Engine. |
| 3    | If WSL needed: installs WSL2 components, registers `RunOnce` key for auto-resume after mandatory reboot.                             |
| 4    | Downloads Ubuntu 22.04 minimal rootfs (~50MB) and imports it as a dedicated `MCBot` WSL distro (isolated from any existing Ubuntu).  |
| 5    | Creates `mc-bot` user non-interactively inside WSL, generates random password, saves to registry and `wsl_credentials.txt`.          |
| 6    | Runs `wsl_docker_setup.sh` inside the MCBot instance to install Docker Engine + Compose plugin.                                      |
| 7    | Prompts for Discord token, RCON password (auto-generate option), Playit key. Writes `.env`.                                          |
| 8    | Runs `docker compose up -d --build` via Docker Desktop or WSL. Prints summary.                                                       |

**Resume logic:** Every completed step is saved to `HKCU\Software\MCBot\Step`. If the process is interrupted (e.g., reboot after WSL install), running `install.bat` again resumes from the exact step it stopped at. Registry is cleaned on success.

**Re-installation protection:** If `Installed=1` is found in registry, the script requires the user to type `YES` exactly three times before proceeding. Any deviation cancels immediately.

### 7.3 `wsl_docker_setup.sh`

Called internally by `install.bat`. Run inside the MCBot WSL instance. Steps:

1. Remove old Docker versions
2. Install prerequisites (ca-certs, curl, gnupg)
3. Add Docker GPG key
4. Add Docker apt repository
5. Install docker-ce, docker-ce-cli, containerd.io, buildx, compose plugin
6. Add `mc-bot` to `docker` group
7. Configure `/etc/docker/daemon.json` (iptables-legacy for WSL, DNS, log limits)
8. Start Docker via `service docker start`
9. Configure `/etc/wsl.conf [boot]` for auto-start on WSL launch
10. Verify `docker --version` + `docker compose version`

### 7.4 `auto_setup.py`

Standalone script that creates Discord structure (roles + channels) without running the full bot. Used as a fallback if `/setup` fails.

```bash
python src/auto_setup.py <BOT_TOKEN> <GUILD_ID>
```

Creates: `Owner`, `Admin`, `Player` roles + `commands`, `console`, `debug`, `server-information`, `backups` channels.

### 7.5 First-Run Discord Setup

After the bot is online:

1. Run `/setup` in any channel (requires `Administrator` permission)
2. Follow the 7-step wizard: platform → version → difficulty → seed → max players → advanced → install
3. Bot creates all channels, downloads server JAR, writes `server.properties`, starts the MC server
4. `/status` should show 🟢 Online after ~30 seconds

---

## 8. Cog Reference

### `cogs/admin.py`

Commands: `/sync`, `/backup_now`, `/logs`, `/whitelist_add`

`/logs` uses `docker logs --tail N mc-bot`, falls back to reading `mc-server/logs/latest.log` via `aiofiles` if Docker call fails. Output sent to log channel.

### `cogs/ai.py`

Optional. Requires `xai-sdk` and `XAI_API_KEY`. Wraps xAI Grok API. System prompt makes it "fully unhinged Minecraft assistant." Responses truncated at 2000 chars.

### `cogs/automation.py`

Two systems:

- **Weekly MOTD**: `tasks.loop(hours=168)` generates AI MOTD via Grok → RCON `setmotd`. Requires a server plugin (Essentials/CMI) for runtime MOTD changes.
- **Trigger scanner**: Subscribes to `LogDispatcher`, scans each log line for phrases defined in `user_config['triggers']`. On match, fires the mapped RCON command.

### `cogs/backup.py`

- **Scheduled**: `tasks.loop(minutes=1)` checks every minute if `now.strftime("%H:%M") == backup_time`. Prevents double-fires by checking `bot_config['last_auto_backup']` against today's date.
- **Manual**: `/backup` command → `backup_manager.create_backup()` → shows `BackupDownloadView` button.
- **Retention**: Auto backups in `backups/auto/` are deleted after `backup_keep_days` days. Custom backups in `backups/custom/` are never auto-deleted.

### `cogs/console.py`

Subscribes to `LogDispatcher`. Parses MC log format `[HH:MM:SS] [Thread/LEVEL]: Message`. Features:

- Batches messages (max 10 or 2 second interval) before sending to Discord to reduce API calls
- Strips blacklisted messages (`user_config['log_blacklist']`)
- Detects join/leave events → updates `bot_config['online_players']`, updates presence, sends event notification to debug channel
- Detects death events (checks 20+ death keywords) → sends to debug channel
- `/cmd` command: owner-only RCON execution, audit-logs user + command to debug channel

### `cogs/control_panel.py`

Sticky control panel in `COMMAND_CHANNEL_ID`. Refreshes every 2 minutes. Tries to `fetch_message` by cached ID and edit; if not found, cleans old bot messages and posts new one. Permission check in `_check_perm()` mirrors `has_role()` logic for button interactions.

### `cogs/economy.py`

- **Balance/Pay**: Stored in `bot_config['economy']` as `{discord_user_id: balance}`. Pay is guarded by `asyncio.Lock`.
- **Word Hunt**: Random interval (30–90 min), requires ≥1 online player. Announces target word via `tellraw`, subscribes temp queue to `LogDispatcher`, first player to type the word in chat wins 100 coins. Winner lookup via `bot_config['mappings']` (MC name → Discord ID). If not mapped, no coins awarded.

### `cogs/events.py`

Events stored in `bot_config['events']` as list of dicts. `tasks.loop(minutes=1)` checks all events. Sends reminders at 24h and 1h before event time. Tracks `reminded_24h` and `reminded_1h` flags per event. Cleans events >24h past.

### `cogs/help.py`

Builds dynamic help embed by cross-referencing user's roles against `config.ROLE_PERMISSIONS`. Only shows commands the user has permission to use. Categorizes commands into sections.

### `cogs/info.py`

`/info` uses `psutil` for system metrics (CPU %, RAM %, Disk %). Tries to get IP from `PlayitCog.tunnels`. Gets seed from `server.properties`. Gets spawn from `bot_config`. Gets TPS via RCON (TODO: vanilla doesn't have `/tps`, only Paper/Forge do). Also triggers `ServerInfoManager.update_info()` to refresh the info channel.

### `cogs/management.py`

Wraps `bot.server.start()`, `stop()`, `restart()`. Each command updates the `#server-information` channel via `ServerInfoManager` on success.

### `cogs/mods.py`

`/mods` traverses `mc-server/mods/` or `mc-server/plugins/` (based on platform) and lists `.jar` files in a Discord embed.

### `cogs/players.py`

`/players` sends the `list` command via RCON, parses the online players, and builds a formatted embed. Handles "0 players online" gracefully.

### `cogs/playit.py`

Fetches the tunnel address from the Playit API (`api.playit.gg/account/tunnels`) via HTTP using the agent's authentication key stored in `/app/data/playit_secret.key` or `.env`. Caches the address with a **2-hour TTL** (`CACHE_TTL = 7200`). After 2 hours, the next `/ip` call re-fetches from the API. Exposed via `self.tunnels` list for other cogs (used by `/info`).

`fetch_playit_address()` returns a `(address, error_message)` tuple. On failure, specific error messages are returned:
- No secret key → instructs user to run installer or add key file
- 401 Unauthorized → key may be expired or invalid
- Non-200 status → tunnel may not be claimed
- Empty tunnel list → no tunnels configured
- No address on tunnel → tunnel still initializing
- Network error → internet connectivity issue

### `cogs/settings.py`

Implements the interactive `/settings` command utilizing multiple Modals (`RamModal`, `ScheduleModal`, `TimezoneModal`, `PermissionsModal`). Directly modifies `user_config.json` via the `config` singleton and hot-reloads running state variables (Java heap, logic intervals, timezone lookups) without requiring a restart.

### `cogs/setup.py`

Entry point for `/setup`. Checks for `server.jar` existence — if found, shows reinstall warning with Confirm/Cancel. Calls `fetch_versions()` from `setup_views.py` to pre-fetch version list, then launches the zero-emoji, real-time reactive `SetupView`. Temporarily ignores Forge API.

### `cogs/stats.py`

Stats flow:

1. Resolve player → UUID (check `bot_config['mappings']` → Mojang API → offline UUID generation)
2. Read `world/stats/<uuid>.json` for playtime, deaths, kills
3. Read `world/playerdata/<uuid>.dat` via `nbtlib` for NBT data
4. Display with skin thumbnail from `crafatar.com` (premium) or placeholder (offline)

### `cogs/tasks.py`

Background tasks started from `on_ready` (not `__init__`):

- `crash_check` (every 30s): If server not running and not intentionally stopped → attempt restart → notify debug channel. After 2 failed restarts, pings server owner and aborts. Also monitors the Playit tmux session with the same pattern: tracks `playit_restart_attempts`, verifies restart success after 3s delay, notifies owner after 2 failures.
- `monitor_server_log` (every 1s): Reads `mc-server/logs/latest.log` incrementally (file position tracking). Detects join/leave/done/stopping events. Sends to log channel. Updates info channel.
- `daily_backup` (commented out): `tasks.loop(time=...)` using pytz timezone. Disabled — `backup.py` handles scheduling more robustly.

---

## 9. Source Module Reference

### `src/backup_manager.py`

`BackupManager` singleton (`backup_manager`).

- `create_backup(custom_name=None)` → `(success, filename, filepath)`. Zips world folder asynchronously via `asyncio.to_thread`. Skips `session.lock`. Validates that the world directory exists before zipping (raises `FileNotFoundError` if missing — fixed in v2.7.1, previously created empty backups silently).
- `upload_backup(filepath)` → URL string via `pyonesend.OneSend().upload()`.
- `_cleanup_auto_backups()` → deletes files older than `BACKUP_RETENTION_DAYS`.
- Backup dirs: `BACKUP_DIR/auto/` and `BACKUP_DIR/custom/` where `BACKUP_DIR = /app/backups`.

### `src/config.py`

Singleton `Config` class. See [Section 4](#4-configuration-system). Also contains `validate_user_config(data)` standalone function.

### `src/installer_views.py`

Multi-step UI components for the install wizard:

- `PlatformSelectView`, `VersionSelectView`, `ServerSettingsView`, `AdvancedSettingsModal`, `WhitelistInputModal`, `InstallationManager`
- These are the older views. `src/setup_views.py` is the modern replacement with full Select menus.

### `src/log_dispatcher.py`

`LogDispatcher` singleton (`log_dispatcher`). See [Section 3.2](#32-log-dispatcher).

### `src/logger.py`

Custom logger with:

- Daily rotation (TimedRotatingFileHandler, `when='midnight'`)
- Custom namer: organizes rotated logs into `logs/YYYY-MM/` subdirectories
- Monthly auto-zip: previous month's directory zipped to `logs/YYYY-MM_logs.zip`
- `StreamToLogger`: redirects `sys.stderr` to logger at ERROR level
- Format: `[HH:MM:SS - DD.MM.YYYY] LEVEL    message`

### `src/mc_installer.py`

`MinecraftInstaller` singleton (`mc_installer`).

- `get_latest_version(platform)` → string (Paper API / Mojang manifest / Fabric meta)
- `download_server(platform, version, callback)` → `(bool, str)` with progress callback
- `_download_paper()`, `_download_vanilla()`, `_download_fabric()`, `_download_forge()` (forge: stub, returns error)
- `accept_eula()` → writes `eula.txt`
- `configure_server_properties(settings)` → writes/merges `server.properties`
- `add_to_whitelist(username)` → Mojang API for online mode, MD5 UUID for offline mode

### `src/mc_manager.py`

After refactoring, this module is now a thin helper containing only `get_server_properties() → dict | None` which reads and parses `server.properties`. The old `mc_manager` server instance was removed.

### `src/server_info_manager.py`

`ServerInfoManager(bot)`:

- `update_info(guild)` → posts/edits plain-text message in `#server-information` channel. Shows: address, version, seed, spawn, world spawn.
- `set_spawn(x, y, z)` → saves to `bot_config`, calls `update_info()`.
- `_get_version()`, `_get_seed()`, `_get_spawn()`, `_get_world_spawn()` → read from config/server.properties.

### `src/server_tmux.py`

`TmuxServerManager`:

- All tmux operations use `subprocess.run` (synchronous) wrapped in `asyncio.to_thread` or `loop.run_in_executor`.
- State file: `mc-server/bot_state.json` → `{"intentional_stop": bool}`.
- Start command: `cd /app/mc-server && java -XmsXXX -XmxXXX -jar server.jar nogui` inside tmux.
- Stop: sends `stop` RCON command, waits 5s, kills tmux session if still alive.
- `is_running()`: checks `tmux has-session -t minecraft` return code.

### `src/setup_helper.py`

`SetupHelper(bot)`:

- `ensure_setup(guild)` → creates/finds roles (MC Admin, MC Player), category (Minecraft Server), channels (command, log, debug). Returns dict of IDs.
- `_assign_admin_role(guild, role)` → assigns MC Admin to guild owner and any member with a role named "Owner".

### `src/setup_views.py`

Modern multi-step Discord form. See [Section 3.6](#36-setup-wizard-flow). Uses `SetupState` dataclass for form state. Fetches version list from Modrinth API on first load.

### `src/utils.py`

Key functions:

- `has_role(cmd_name)` → `app_commands.check` decorator. 3-step check: ID map → name map → @everyone.
- `rcon_cmd(cmd)` → async RCON via `aiomcrcon.Client`. Returns response string or error.
- `send_debug(bot, msg)` → send to debug channel + log.
- `get_uuid(username)` → looks up in `usercache.json`.
- `parse_server_version()` → reads `latest.log` line by line for "Starting minecraft server version".

### `src/version_fetcher.py`

`VersionFetcher` singleton with 1-hour cache per platform. Methods: `get_versions(platform, limit)`, `get_latest_version(platform)`. Fallback to hardcoded list if API fails.

---

## 10. Known Bugs & Technical Debt

### 10.1 Previously Fixed Critical / Security Issues — ✅ RESOLVED

| #   | Bug / Issue                                       | Resolution                                                                                                                                     |
| --- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Exposed RCON port 25575 on Host                   | `docker-compose.yml` updated to ensure port is only accessible inside container at `127.0.0.1`.                                                |
| 2   | Duplicate Log Instances per Cog                   | Replaced scattered `docker logs -f` calls with centralized `src/log_dispatcher.py` instance to handle streams efficiently via `asyncio.Queue`. |
| 3   | Duplicate Server Manager Instance                 | Removed the extra `mc_manager.py` ghost instance. Forced everything to query `bot.server`.                                                     |
| 4   | `config.py` Silently Overwriting Simulation State | `load()` and `save_bot_config()` were locked together, overwriting `--simulate` flags. Now state resets are preserved correctly.               |
| 5   | JSON Economy Race Condition                       | Wrapped JSON reads/writes with `asyncio.Lock` since all bot reads/writes happen sequentially in the same Thread.                               |
| 6   | missing `OWNER_ID` population                     | Defined logic in `setup_helper.py` to identify Guild owner.                                                                                    |

### 10.2 Logic Bugs -- Pending / Under Review

| #   | File                    | Bug                                                                                                                                      | Status       |
| --- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| 1   | `src/backup_manager.py` | Backup dir mismatch: Docker volume mounts `./backups:/app/backups`. Ensure `config.SERVER_DIR` stays relative to absolute Docker setups. | Open         |
| ~~2~~   | ~~`src/backup_manager.py`~~ | ~~`_zip_world()` silently created empty backups when world directory didn't exist.~~ | FIXED v2.7.1 |
| 2   | `cogs/automation.py`    | `cog_unload()` references `self.log_task` but also `self.log_scan_task` -- inconsistent naming. One is never cancelled.                  | FIXED v2.6.0 |
| 3   | `cogs/info.py`          | Vanilla MC has no `/tps` RCON command -- TPS section in `/info` silently skips correctly, but should theoretically read the difference.  | Open         |
| 4   | `cogs/console.py`       | If `LOG_CHANNEL_ID` is None on startup, tail loop busy-waits with `asyncio.sleep(10)` without exponential backoff.                       | FIXED v2.6.0 |
| 5   | `cogs/stats.py`         | `get_uuid_online` uses `aiohttp` but no explicit timeout -- hangs if Mojang API goes down completely.                                    | FIXED v2.6.0 |

### 10.3 Code Quality -- Low Priority

- ~~`cogs/console.py` has duplicate `from datetime import datetime` imports.~~ FIXED v2.6.0
- ~~`src/server_info_manager.py` has leading whitespace on line 1.~~ FIXED v2.6.0
- `cogs/help.py` categories list hardcodes command names -- won't auto-update when commands are added.

---

## 11. Version History & Recent Changes

### v2.7.2 -- Setup Flow & Polishing Update _(Current)_

**Setup UX Improvements:**
- Removed all emojis from the `/setup` flow (dropdowns, buttons, titles) for a cleaner, professional look.
- Version dropdown now correctly displays the resolved version alongside `(latest)` (e.g., `1.21.4 (latest)`).
- Complete UI reactivity: All Selects and Modals in `setup_views.py` now instantly edit the embed to show the "Current Selection", eliminating visual input lag.
- After server startup during installation, the bot now polls RCON readiness for up to 60 seconds. This ensures the embedded Control Panel perfectly synchronizes and shows "Online" immediately upon completion.

**Log Latency & Bug Fixes:**
- Re-architected `src/log_dispatcher.py` to use a `tail -F` subprocess instead of Python sleep polling, reducing Discord log channel latency from 1s to ~instant.
- Reduced `console.py` log batch dispatch interval from 1.0s to 0.5s for faster log visualization.
- Fixed a logic bug in `cogs/tasks.py` crash checker where variables were accessed before assignment.
- Upgraded `install.sh` to intelligently detect existing installations, prompting the user to either fully Reconfigure, Update Code (git pull + rebuild), or Cancel.

### v2.7.1 -- Playit Reliability & Testing Release

**Playit.gg Improvements:**

- Upgraded Playit crash recovery in `cogs/tasks.py` to match MC server pattern: attempt counter (`playit_restart_attempts`), owner notification after 2 failures, 3-second restart verification, counter reset when healthy.
- Added 2-hour cache TTL to `/ip` command in `cogs/playit.py` (`CACHE_TTL = 7200`). Previously cached forever.
- Added specific error messages to `/ip` for all failure modes (no key, 401, no tunnels, network error, initializing).
- Simplified `install.sh` Playit prompt: now asks Yes/No "Do you have a key?" instead of confusing "paste your key or leave blank".

**Bug Fixes:**

- Fixed `backup_manager._zip_world()` silently creating empty backups when world directory didn't exist. Now raises `FileNotFoundError`.

**Testing:**

- Added Docker-based test suite: `Dockerfile.test`, `docker-compose.test.yml`, 48 tests across 4 modules (config validation, backup manager, version fetcher, utilities).
- Added `Makefile` with `make test`, `make test-verbose`, `make test-single` targets.

### v2.6.0 -- Bug Fix & Hardening Release _(Current)_

28-issue comprehensive bug fix and code hardening pass based on senior code review (`overview.md`).

**Critical Fixes:**

- Fixed tuple unpack crash in `cogs/tasks.py` `daily_backup` (was unpacking 2 values, `create_backup()` returns 3).
- Added `import asyncio` at module scope in `src/setup_views.py` (was imported locally, causing `NameError` in `_save_config_to_file`).
- Fixed `cogs/automation.py` attribute mismatch (`log_scan_task` vs `log_task`), added `log_dispatcher.unsubscribe()` to prevent memory leak.
- Added `./data:/app/data` volume mount in `docker-compose.yml` -- config was being lost on every rebuild.

**Significant Fixes:**

- Added `aiohttp.ClientTimeout` to all API calls in `stats.py` (10s) and `mc_installer.py` (30s class constant).
- Replaced deprecated `bot.loop.create_task()` with `asyncio.create_task()` in `economy.py`.
- Removed empty `word_hunt_task` loop in `economy.py` (loop body was `pass`).
- Fixed `GUILD_ID` type inconsistency in `setup_helper.py` (was stored as string, now int).
- Added `installed_platform` saving to config during setup in `setup_views.py`.
- Replaced unsafe `os.execv` bot restart with `sys.exit(0)` + Docker restart policy in `management.py`.
- Added exponential backoff (10s-120s) to `console.py` channel wait loop.
- Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()` in `console.py`.

**Code Quality:**

- Removed duplicate `datetime` import in `console.py`.
- Fixed AI error typo in `ai.py` ("efficient" -> "No valid API key or SDK found.").
- Removed leading whitespace in `server_info_manager.py`.
- Removed dead `mcrcon` package from `requirements.txt` (only `aio-mc-rcon` is used).
- Added `mem_limit: 256m` to playit service in Docker Compose.
- Commented out Forge references with documentation for Modrinth and Forge Maven APIs.

**Dead Code Removal (~500 lines):**

- Deleted `src/installer_views.py` (~400 lines, fully replaced by `setup_views.py`).
- Removed `monitor_server_log` + `_process_log_line` + `send_log` from `tasks.py` (~90 lines, duplicated by `console.py`).
- Removed orphaned imports (`time`, `pytz`, `dt_time`, `aiofiles`, `random`) from `tasks.py` and `automation.py`.

**Crash-Proofing:**

- Enhanced `bot.py` `__main__` block with formatted crash message and `Press Enter to close` on both crash and normal shutdown.
- All cog `cog_unload` methods now guard with `hasattr` against missing attributes.

**Infrastructure:**

- `install.bat` replaced with friendly "Windows not supported yet" fallback + pseudocode for future WSL flow.

### v2.5.5 -- Core Capabilities & Control Panel Update

_(Cumulative architectural adjustments addressing Phases 1-7 refactoring sessions)_

- **Control Panel**: Deployed sticky, interactive `#command` channel Discord UI (`cogs/control_panel.py`) serving Start, Stop, Restart, Status buttons.
- **Dynamic Integration**: Connected `cogs/info.py` to seamlessly read active Playit.gg domains from `cogs/playit.py`. Removed IP hardcoding.
- **Dynamic Versions**: Swapped hardcoded fallback version dropdowns for live Modrinth API fetching targeting both Vanilla and Paper platforms (`src/setup_views.py`).
- **Setup Reliability**: Supported offline-mode whitelist implementation by generating consistent local MD5 UUID hashes in `mc_installer.py`. Temporarily muted buggy Forge downloads until their API standardizes.
- **Code Sweeping**: All files swept for redundant conversational comments. Forced data files strictly inside the `data/` path to avoid root pollution. Replaced `--dry-run` flag with proper `--simulate` parameter. Completed unification of logs through the centralized `LogDispatcher`.
- **Install Improvements**: Upgraded `install.sh` to apply docker group permissions seamlessly without requiring user logouts, and ensured Docker service starts immediately upon download.

### v2.5.4 — Stability & Windows Support

- Enhanced `install.bat` to verify Docker before attempting WSL setup.
- Added numbered step indicators in all installers.
- Fixed unbuffered output (`PYTHONUNBUFFERED=1`) preventing hanging installations.

### v2.5.3 — Cleanup Update

- Initial code cleanups: `config_generator.py` (dead code) and duplicate configurations deleted.

### v2.5.2 — Automation Update

- Added `cogs/events.py` for `/event_create`, `/event_list`.
- Added weekly MOTD generation via Grok (`cogs/automation.py`).
- Added Regex chat trigger system.

### v2.5.1 — Security & Architecture

- Centralized read-write concurrency via `FileLock`.
- Deprecated loose legacy structures. Added Healthcheck validation.

### v2.5.0 — Advanced Features

- Released full `/stats` mapping with NBT Parsing + `/playit` bindings + Economy Word Hunt games.

### v2.0.0 — Migrated to discord.py v2.0

- Replaced classic `@commands.command` with full `/` app slash commands + Ghost mode `--simulate` parameters.

---

## 12. Completed Features

- ✅ Process Management (Start/Stop/Restart) via tmux
- ✅ RCON Communication (`src/utils.rcon_cmd`)
- ✅ Thread-safe Config System (`filelock`)
- ✅ Unified Installer: Linux `install.sh` (with Reconfigure/Update detection) + Windows `install.bat`
- ✅ Modrinth API Integration + Progress tracking in setup wizard
- ✅ **Setup Flow UI**: Emoji-less, instantaneous UI reactivity with RCON readiness synchronization
- ✅ **Live Log Tailing**: Zero-latency `tail -F` subprocess → Discord channel (batched 0.5s)
- ✅ Hardware Info (CPU/RAM/Disk via `psutil`)
- ✅ NBT Data Parsing (Offline/Cracked accounts via `nbtlib`)
- ✅ World Backup (zip, scheduled, manual, retention cleanup)
- ✅ Owner-only `/cmd` with audit logging
- ✅ Event Scheduling with 24h + 1h reminders + Automations + Trigger Tracking
- ✅ Offline mode whitelist (MD5 UUID generation, no Mojang dependency)
- ✅ Simulation / Ghost Mode for local CI/CD tests without MC Servers
- ✅ RCON Port protection + Docker container isolation

---

## 13. TODO — Active Roadmap

### 🟠 High Priority

- [ ] **SQLite via `aiosqlite`** — replace `bot_config.json` economy and events storage arrays outright. JSON has minor race conditions under rapid concurrent loads, even with limits.
- [ ] **Minecraft→Discord chat bridge** — pipe in-game chat to a Discord channel directly, scanning logs.
- [ ] **Player linking system** — `/link <mc_username>` command. Require Discord accounts mapped to MC usernames for Word Hunt bounds.
- [ ] **Mascan-proof the offline whitelist** — add a secondary verification layer for proxied connections implying BungeeCord/Velocity setups where standard MD5 hashes are bypassed for premium connections.
- [ ] **Full Translation Support (i18n)** — Extract English responses to a JSON/YAML locale file so the bot logic works transparently anywhere globally.

### 🟡 Medium Priority

- [ ] **Windows Native Installer (install.ps1)** — Full PowerShell script utilizing `dism.exe` for WSL/VirtualMachinePlatform enabling, Ubuntu installation natively, and colorized UI blocks.
- [ ] **Cloud Storage Synchronization** — Background async uploading of generated backups to Google Drive using standard Python API integration.
- [ ] **Server uptime statistics** — track uptime start time, display in `/info`.
- [ ] **Performance metrics dashboard** — periodic embed showing TPS trend, player count over time, RAM usage history.
- [ ] **Allowlist request system** — Discord UI modal allowing external users to request entry without Admin manipulation.
- [ ] **Scheduled announcements** — `/announce_schedule <time> <message>`.

### 🟢 Low Priority / Nice-to-Have

- [ ] **Death counter leaderboard** — `/deaths` command showing top 10 most-died players from NBT stats.
- [ ] **Vote command** — `/vote <question> [option1] [option2] ...` — creates poll in-game via `tellraw`.
- [ ] **Complete LogDispatcher Unit Testing** — specifically mock its output and verify its event firing reliability.

---

## 14. Development Workflow & Rules

### File Usage Rules

1. **Never import specific legacy functions** from obsolete files like `config_generator.py` or `utils/` folder equivalents that have been deleted. Stick entirely to `src/utils.py`.
2. **Configuration loading** must be explicitly isolated. Use `config.load_bot_config()` or `config.load_user_config()` exclusively.
3. Don't manipulate `dry_run` variables internally; access `config.dry_run`.

### Setting Up Local Dev Environment

```bash
git clone https://github.com/slogiker/mc-bot.git
cd mc-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Running in Simulation Mode

No Docker, no real server needed:

```bash
python bot.py --simulate
```

In simulation mode:

- `MockServerManager` handles all server commands (fake delays, no processes)
- Bot fully connects to Discord and registers slash commands
- All commands work except ones that invoke RCON or write server files natively.

### Adding a New Command

1. Create a cog file in `cogs/`
2. Add `@app_commands.command(name="...", description="...")`
3. Decorate with `@has_role("your_cmd_name")`
4. Add `"your_cmd_name"` to the appropriate role in `data/user_config.json`

---

## 15. Deployment Notes

### Docker Volume Mounts

```yaml
volumes:
  - ./mc-server:/app/mc-server # Minecraft server + world data
  - ./backups:/app/backups # World backups
  - ./logs:/app/logs # Bot logs
  - ./data:/app/data # Bot config (persisted across rebuilds since v2.6.0)
  - ./.env:/app/.env # Secrets
```

**Important:** As of v2.6.0, the `data/` directory is mounted as a volume. Config files (`bot_config.json`, `user_config.json`) are persisted across rebuilds. This was previously the most dangerous bug -- configs were lost on every `docker compose build`.

### Network Architecture

```
Host machine
  └─ mc-bot container
       ├─ Python bot process
       ├─ tmux session "minecraft"
       │    └─ java server.jar (MC server, port 25565)
       └─ RCON listener 127.0.0.1:25575
```

25575/tcp remains internal only and is highly protected.

### Healthcheck

Docker restarts the container automatically after 3 failed `psutil` checks probing PID 1.



---

## AI Agent Prompt Instructions

> **System Instruction for all AIs:** At each change, add recent architectural or functional changes to this file (`docs/information.md`),and keep track of versions, update to and if broadly applicable, append new features to `README.md`. This `information.md` file can always be longer (or same size), never shorter. It must remain the comprehensive canonical source of truth for the codebase history and technical roadmap. Maintain this documented style, structure, and depth explicitly going forward.
