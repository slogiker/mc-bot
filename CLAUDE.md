# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MC-Bot is a Discord bot that manages a Minecraft server, all running in a single Docker container. The bot communicates with the Minecraft server via RCON (localhost only, never exposed), controls the server process through tmux, and streams logs to Discord channels.

## Common Commands

```bash
# Run all tests (Docker-based, auto-cleanup)
make test

# Run tests with verbose output
make test-verbose

# Run a single test file
make test-single FILE=tests/test_config.py

# Start bot locally (without filesystem changes)
python bot.py --simulate

# Build and start Docker container
docker compose up --build

# View logs
docker compose logs -f
```

## Architecture

### Startup Flow (`bot.py`)
1. Parse args (`--simulate` enables mock mode)
2. Instantiate `MinecraftBot` with either `TmuxServerManager` (real) or `MockServerManager` (simulate)
3. `setup_hook()` — loads all cogs dynamically from `cogs/`
4. `on_ready()` — creates Discord roles/channels via `SetupHelper`, resolves permissions, syncs slash commands, starts background tasks

### Key Abstractions

- **`src/server_interface.py`** — Abstract base for server control (`is_running`, `start`, `stop`, `restart`, `send_command`). Two implementations: `TmuxServerManager` (production) and `MockServerManager` (testing).
- **`src/config.py`** — Singleton config manager. Loads `data/bot_config.json` (guild/channel IDs, runtime state) and `data/user_config.json` (user preferences, RAM, backup schedule, role permissions). Uses `FileLock` for safe concurrent access.
- **`src/log_dispatcher.py`** — Singleton that tails Docker logs and fans output out to multiple `asyncio.Queue` subscribers. Start it before subscribing.
- **`src/log_watcher.py`** — Subscribes to `LogDispatcher`, parses player login events, fires `on_minecraft_player_login` Discord bot events.
- **`src/join_guard.py`** — Intercepts player logins (via `log_watcher`), sends DM verification challenges for offline-mode servers. Depends on `mc_link_manager`.
- **`src/backup_manager.py`** — Async zip-based world backups with configurable retention (auto vs. custom backups tracked separately).

### Cogs (`cogs/`)
Each file is a discord.py `Cog` loaded dynamically. Commands are registered as slash commands synced to the guild.

| Cog | Role |
|-----|------|
| `management.py` | `/start`, `/stop`, `/restart` |
| `tasks.py` | Background loops: crash detection, log streaming, daily backups, auto-restart |
| `console.py` | `/cmd` raw RCON, live log tail |
| `setup.py` | Interactive setup wizard (multi-step Discord UI) |
| `stats.py` | Player stats via NBT file parsing + Mojang API skin lookup |
| `link.py` | Discord↔Minecraft account linking |
| `backup.py` | `/backup`, `/backup_list`, `/backup_download` |

### Data Files (`data/`)
- `bot_config.json` — Machine state: guild ID, channel IDs, player lists
- `user_config.json` — User preferences: RAM, backup schedule, timezone, role permissions
- `mc_links.json` — Discord↔Minecraft username linkage (auto-created by `MCLinkManager`)
- `bot_state.json` — Server process state: intentional stop flag, start timestamp

### Permission System
Role-based. `has_role()` in `src/utils.py` checks if a Discord member has any role whose name appears in `user_config["permissions"][command_name]`. Configured per-command during setup.

### RCON Communication
All server commands go through `src/utils.py` → `aio-mc-rcon`. RCON runs on `127.0.0.1:25575` (container-internal only, never exposed to host).

### Testing
- Framework: pytest with fixtures in `tests/conftest.py`
- Key fixtures: `valid_user_config` (full config dict), `temp_world_dir` (fake world with `level.dat` + `region/`)
- Tests run in Docker via `docker-compose.test.yml` / `Dockerfile.test` — no local Python deps needed beyond `make`
- `MockServerManager` (and `--simulate` flag) allows testing bot behavior without tmux or a real Minecraft install

## Environment Variables

Defined in `.env` (copy from `.env.example`):
- `BOT_TOKEN` — Discord bot token
- `RCON_PASSWORD` — Must match `server.properties`
- `PLAYIT_SECRET_KEY` — Optional, for Playit.gg tunnel

## Docker Layout

Single container runs:
- Python bot process
- Minecraft server in tmux session `minecraft`
- Optional Playit.gg agent in tmux session `playit`

Volumes: `mc-server/`, `backups/`, `logs/`, `data/`, `.env`
