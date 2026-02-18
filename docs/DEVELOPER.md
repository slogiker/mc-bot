# Developer Documentation

**Repository**: `mc-bot`
**Version**: v2.5.6
**Last Updated**: February 16, 2026

---

## 📖 Overview

This is a **self-hosted Discord bot** designed to manage a local Minecraft Java Edition server. It acts as a bridge between Discord and the server process, providing remote control, monitoring, and automation features.

### Core Philosophy

- **Private Use**: Built for small friend groups, not public servers.
- **Self-Contained**: No external web panels or databases required (uses JSON/Filelock).
- **Direct Control**: Wraps the server JAR process (`subprocess`) and uses RCON for commands.
- **Docker-First**: Recommended deployment via Docker Engine (Linux/WSL 2).

---

## 🛠️ Architecture Deep Dive

### Tech Stack

- **Python + discord.py**: Rapid development of slash commands and asynchronous task management.
- **Subprocess**: The bot _is_ the wrapper. It owns the Java process, capturing STDOUT directly for the log console.
- **Filelock**: Prevents race conditions when multiple async tasks read/write JSON config files.
- **Aiofiles**: Non-blocking log tailing keeps the Discord UI responsive while reading large server logs.
- **Docker**: Container-based deployment with WSL 2 integration on Windows.

### File Structure (v2.5.6)

| Path                     | Description                                                                                                               |
| :----------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| **Root**                 |                                                                                                                           |
| `bot.py`                 | Main entry point. Loads cogs, starts ServerManager, handles shutdown signals.                                             |
| `.env`                   | **Secret** configuration (Discord Token, RCON Password, API Keys).                                                        |
| `requirements.txt`       | Python dependencies.                                                                                                      |
| `docker-compose.yml`     | Docker Compose configuration with cache busting and WSL integration.                                                      |
| `Dockerfile`             | Multi-stage container build with cache invalidation support.                                                              |
| **Install (`install/`)** |                                                                                                                           |
| `install.bat`            | **Windows Bootstrapper**. Installs WSL/Ubuntu, configures Docker, handles reboot, launches `install.sh`.                  |
| `install.sh`             | **Linux Setup**. Installs Docker Engine (if needed), validates Python/Java. Uses unbuffered output for progress tracking. |
| `rebuild.sh`             | **Developer Rebuild**. Checks for unpulled commits, rebuilds with `--no-cache`, and restarts containers.                  |
| `simulate.py`            | **Ghost Mode**. Simulates installation and runs bot in RAM-only simulation mode.                                          |
| **Cogs (`cogs/`)**       | **Discord Command Modules**                                                                                               |
| `console.py`             | Live log streaming, Owner-only RCON (`/cmd`), Presence updates.                                                           |
| `stats.py`               | Player stats (`/stats`). Parses NBT `.dat` files for offline players and hits Mojang API for online.                      |
| `info.py`                | System health (`/info`). Uses `psutil` to check CPU/RAM/Disk usage of the host.                                           |
| `backup.py`              | Backup commands (`/backup`). Triggers zip creation and ephemeral uploads.                                                 |
| `economy.py`             | Balance system (`/pay`) and background "Word Hunt" minigame.                                                              |
| `ai.py`                  | AI integration. Uses `xai-sdk` to chat with Grok (`/ai`) and generate MOTDs.                                              |
| `events.py`              | Scheduling system (`/event`) with auto-reminders (24h/1h).                                                                |
| `automation.py`          | Background tasks: AI MOTD updates and custom Regex Chat Triggers.                                                         |
| `management.py`          | Control panel commands (Start/Stop/Restart).                                                                              |
| `setup.py`               | Setup wizard for completely new installations.                                                                            |
| **Src (`src/`)**         | **Core Logic & Helpers**                                                                                                  |
| `backup_manager.py`      | Handles Zipping world folders and interactions with `pyonesend`.                                                          |
| `server_info_manager.py` | Updates the persistent "Status" channel embed.                                                                            |
| `logger.py`              | Centralized logging configuration.                                                                                        |
| `utils.py`               | RCON wrapper, file helpers, role checkers.                                                                                |
| `version_fetcher.py`     | Dynamically fetches Minecraft server versions from APIs with intelligent fallbacks.                                       |
| `mc_installer.py`        | Manages Minecraft server installation and version resolution.                                                             |
| **Utils (`utils/`)**     |                                                                                                                           |
| `config.py`              | **Thread-safe** `load/save` for JSON configs using `FileLock`.                                                            |
| **Data (`data/`)**       | **Persistent Storage**                                                                                                    |
| `bot_config.json`        | Core bot state: Economy balances, Event lists, Setup flags.                                                               |
| `user_config.json`       | User preferences: Custom triggers, Schedule settings.                                                                     |

---

## ⚙️ Configuration Guide

### `bot_config.json` vs `user_config.json`

- **Bot Config**: Stores _system state_ and _essential logic_ (e.g., economy balances, scheduled events, server directory).
- **User Config**: Stores _user preferences_ (e.g., keyword triggers, backup schedules).

### Environment Variables (.env)

- `BOT_TOKEN`: Required (Discord Bot Token).
- `RCON_PASSWORD`: Required (Auto-generated by installer).
- `XAI_API_KEY`: Optional (Enables Grok features).
- `ONE_SEND_TOKEN`: Optional (Auto-generated for backup uploads).

---

## 🐋 Docker Setup Details

The bot is designed to run in a Docker container for isolation and ease of management.

### Windows Installation (WSL 2)

**CRITICAL**: After running `install.bat`, you must enable Docker WSL integration:

1. Open **Docker Desktop**
2. Go to **Settings > Resources > WSL Integration**
3. Enable "Enable integration with Ubuntu"
4. Click "Apply & Restart"
5. Test: `wsl docker --version`

This step is **REQUIRED** for Docker commands to work in WSL 2.

### Linux Installation

Run `install.sh` directly. It will:

1. Check for Docker installation
2. Install Docker Engine if needed
3. Add your user to the docker group
4. Build and start the container

### Volumes

- `./mc-server`: Maps to `/app/mc-server` (Persistent Minecraft world/data).
- `./backups`: Maps to `/app/backups` (Persistent zip backups).
- `./logs`: Maps to `/app/logs` (Persistent bot logs).
- `./.env`: Maps to `/app/.env` (Configuration file).

### Ports

- **25565**: Minecraft Server (TCP/UDP) - can be remapped or disabled with playit.gg.
- **25575**: RCON (TCP) - Local only, not exposed externally.

### Memory

- Default limit: **8GB**. Adjust in `docker-compose.yml` (`mem_limit`).

### Developer Rebuilds

For developers working on the bot code, use the dedicated rebuild script:

```bash
./install/rebuild.sh
```

This script:

- Checks if you have unpulled commits (suggests `git pull` if behind)
- Stops existing containers
- Rebuilds the Docker image with `--no-cache` (ensures fresh build)
- Starts the containers

> **Note**: Normal users should use `install.sh` which uses Docker caching for faster builds.

---

## 👻 Simulation / Ghost Mode

For testing or demonstration purposes, the bot can run in a **Simulation Mode** that mimics a full installation and server without modifying the host system.

### How to Run

```bash
python install/simulate.py
```

### What it does

1. **Visual Mimicry**: Prints fake installation progress (5 steps) identical to the real script.
2. **Transient Token**: Prompts for a Discord Token securely. This token is **NEVER saved to disk**, only held in RAM.
3. **Bot Simulation**: Launches `bot.py --simulate`.
   - Connects to Discord using the transient token.
   - Responds to commands (`/start`, `/stop`, etc.) with success messages.
   - **NO** files are created/modified (`.env`, `config.json`).
   - **NO** server/java process is started.

### Use Cases

- Testing Discord permissions/commands without a real server.
- Demonstrating the setup flow to users safely.
- Development of new commands without needing a heavy server running.

### Progress Tracking in All Installers

All installation scripts now include clear step indicators:

**Windows (`install.bat`)**:

- STEP 1/4: Checking Docker configuration
- STEP 2/4: Checking Docker WSL integration
- STEP 3/4: Preparing Linux setup in WSL
- STEP 4/4: Running Linux installation script

**Linux (`install.sh`)**:

- STEP 1/4: Building Docker image (with build progress)
- STEP 2/4: Starting containers
- STEP 3/4: Waiting for container to initialize
- STEP 4/4: Verifying container status

**Simulation (`simulate.py`)**:

- STEP 1/5: Checking system requirements
- STEP 2/5: Checking Docker configuration
- STEP 3/5: Updating package lists
- STEP 4/5: Setting up configuration
- STEP 5/5: Starting Bot in SIMULATION MODE

---

## 🔄 Minecraft Server Versions

The bot supports dynamic version fetching from official APIs:

### Version Resolution

1. **Paper Server**: Fetches from Paper API (https://api.papermc.io/v2/projects/paper)
2. **Vanilla Server**: Fetches from Mojang Launcher Meta (https://launchermeta.mojang.com/mc/game/version_manifest.json)
3. **Fabric Server**: Uses Vanilla versions with Fabric loader support

### Version Selection

In the Discord setup wizard (`/setup`), users can:

- Select from **latest** (auto-resolves to newest available)
- Choose from recent versions (1.21.11, 1.21.10, 1.21.9, etc.)
- Enter a custom version (e.g., 1.20.4)

### Fallback Versions

If APIs are unreachable:

```python
["1.21.11", "1.21.10", "1.21.9", "1.21.8", "1.21.7", "1.21.6", "1.21.5", "1.21.4", "1.20.4"]
```

---

## 📜 Version History & Changelog

### v2.5.4 (Current) - _The "Stability & Windows Support" Update_

- **Windows Installation**:
  - Added comprehensive Docker WSL integration detection and guidance.
  - Enhanced error handling for missing Docker Desktop.
  - Added Docker verification step before WSL setup.
- **Progress Tracking**:
  - All installers now show clear numbered steps.
  - Added progress indicators during Docker build.
  - Unbuffered output in install.sh for real-time visibility.
  - simulate.py now shows 5-step process matching real installation.
- **Minecraft Versions**:
  - Updated hardcoded versions from 1.21.5 to 1.21.11 (latest).
  - Added intermediate versions (1.21.6-1.21.10).
  - Improved fallback version list in version_fetcher.py.
- **Docker & Caching**:
  - Improved cache busting mechanism in docker-compose.yml.
  - Added CACHEBUST argument to Dockerfile.
  - Better build layer caching for dependencies.
- **Documentation**:
  - Comprehensive Windows WSL setup instructions.
  - Docker integration troubleshooting guide.
  - Version resolution documentation.
  - Installation progress tracking documentation.

### v2.5.6 (February 16, 2026) - Major Overhaul

**Permissions & Commands:**

- Implemented 4-tier role hierarchy: Owner → Admin → Player → @everyone
- Fixed `set_spawn` command permission decorator
- Fixed `/seed` to read from `server.properties` (works offline)
- Improved `/info` UI: removed backticks, added emoji player list format
- Added `control` and `set_spawn` to permission system

**Logging System:**

- **Standardized Log Reading**: `admin.py`, `automation.py`, and `economy.py` now all use `docker logs -f` subprocesses to read server output. This eliminates file locking issues and race conditions associated with reading `latest.log` directly.
- **Console Service**: `cogs/console.py` provides the main live log stream to Discord.
- **Robustness**: All log readers handle subprocess lifecycles and restart on failure.

**Permissions System:**

- **Role ID Support**: `src/utils.py` `has_role` decorator now prioritizes Role IDs configured in `bot_config.json` (via `ROLES` map) over Role Names.
- **Fallback**: Retains backward compatibility by checking Role Names if IDs fail.
- **Debug**: Failsafe checks log to the debug channel if a user has sufficient expected permissions but fails the check.

**Scheduled Tasks:**

- **Backups**: `cogs/backup.py` runs a 1-minute loop checking `user_config.json`'s `backup_time`.
- **Word Hunt**: `cogs/economy.py` runs a random interval loop for community engagement.
- **Events**: `cogs/events.py` checks for scheduled events and sends 24h/1h reminders.

**Server Information:**

- Converted from embed to plain text with Discord markdown formatting
- Added world spawn coordinates from `server.properties` (spawn-x/y/z)
- Visual separators with bold labels and code blocks for values

**Developer Tools:**

- Created `install/auto_setup.py` for automated role/channel creation
- Advanced users can programmatically set up Discord infrastructure

### v2.5.5 (February 16, 2026) - Installation Improvementss tracking documentation.

### v2.5.3 - _The "Cleanup" Update_

- Refactoring: Renamed `scripts/` to `install/`.
- Consolidated installation logic into `install.bat` (Windows/WSL) and `install.sh` (Linux).
- Added Ghost Mode simulation (`install/simulate.py`).
- Deep cleaned root directory.

### v2.5.2 - _Automation & Community_

- Added `cogs/events.py` for scheduling.
- Added `cogs/automation.py` for AI MOTD and Chat Triggers.
- Implemented Context-Aware Triggers (Log scanning).

### v2.5.0 - _Advanced Features_

- Stats: NBT Parsing (`nbtlib`) for offline player data.
- Info: `psutil` integration for real hardware monitoring.
- Backups: `pyonesend` integration for cloud zip sharing.
- Economy: Added "Word Hunt" and Balance system.

### v2.0.0 - _The Rewrite_

- Shifted to `discord.py` 2.0+ (Slash Commands).
- Introduced `cogs` architecture.
- Added `aiofiles` for non-blocking log tailing.

### v1.0.0 - _Legacy_

- Basic start/stop script.
- Single file monolith.

---

## Troubleshooting

### Windows: "Docker not found in WSL"

**Problem**: Running `docker` in WSL returns "command not found" error.

**Solution**:

1. Open Docker Desktop
2. Settings > Resources > WSL Integration
3. Enable "Enable integration with Ubuntu"
4. Click "Apply & Restart"
5. Restart WSL: `wsl --terminate Ubuntu`
6. Test: `wsl docker --version`

### Build Hangs After Credentials

**Problem**: Installation stops after entering Discord token.

**Solution**:

- Scripts now use unbuffered output (`PYTHONUNBUFFERED=1`)
- Check install.sh for proper `set -e` error handling
- Ensure your `.env` file was created: `cat .env`

### Force Rebuild Without Cache

```bash
# Clear Docker buildx cache and rebuild
docker buildx prune -af
CACHEBUST=$(date +%s) docker compose up -d --build
```

### Version Not Found

If a specific version doesn't exist:

1. Check Paper API: https://api.papermc.io/v2/projects/paper/versions
2. Use the Discord `/setup` wizard for automatic resolution
3. Check fallback versions in `src/version_fetcher.py`
