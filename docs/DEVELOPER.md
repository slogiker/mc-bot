# Developer Notes & Architecture

## Overview

This bot uses discord.py to interface with a containerized Minecraft server. It uses `docker-compose.yml` to spin up both the bot and Playit.gg tunneling.

## Project Structure

- `bot.py`: Main entry point
- `src/`: Core logic (Config, ServerInterface, LogDispatcher, SetupHelper)
- `cogs/`: Discord bot commands and event listeners
- `data/`: Configuration files (`bot_config.json`, `user_config.json`)
- `install/`: Helper scripts for initial setup

## Phase 1-4 Changes Summary

### Configuration

- Split config into `bot_config.json` (system state) and `user_config.json` (user preferences).
- Centralized read-write concurrency via `FileLock` inside `src/config.py`.
- Auto-detection of timezone via IP API upon initialization for schedules.
- `role_permissions` now strictly uses names (`MC Admin`, `MC Player`) evaluated to `@has_role` dynamically.

### Log Dispatching

- Replaced multiple spawned `docker logs -f` calls with a single `LogDispatcher` singleton. Cogs like `console`, `automation`, and `economy` now `subscribe()` to a shared queue.

### Economy

- Fixed race condition in word hunt `payload` and `/pay` command using `asyncio.Lock` since all bot reads/writes happen sequentially in the same Thread.
- Moved `word_hunt_task` startup out of `__init__` directly into `cog_load`.

### Security & Setup

- Hidden RCON port from host in `docker-compose.yml`.
- Added Docker healthcheck.
- Added `/cmd` owner audit logging in debug channel.
- Removed legacy duplicate server manager instances (`mc_manager.py`).

### Phase 5: Installation & Setup Logic

- Replaced obsolete `--dry-run` flag with proper `--simulate` boolean for execution mode.
- In `setup_views.py`, implemented dynamic API fetching for Vanilla/Paper versions via Modrinth.
- Supported offline-mode whitelist implementation by generating local MD5 UUID hashes in `mc_installer.py`.

### Phase 6: Code Sweep & Documentation

- Entire codebase swept for legacy conversational AI comments (e.g., `# Let's`, `# We'll`); removed for clean professional logic.
- Documentation consolidated into `/docs`; root `TODO.md` merged and deleted, `Code-Overview.md` integrated and deleted.
- Data files explicitly forced into `data/` instead of polluting the root repository.

### Phase 7: Control Panel & Integrations

- Created an interactive, sticky Discord `ui.View` Control Panel (`cogs/control_panel.py`) serving Start, Stop, Restart, and Status commands in the designated `COMMAND_CHANNEL_ID`.
- Connected `cogs/info.py` to seamlessly read active Playit.gg domains from `cogs/playit.py` so properties don’t need hardcoding in user configurations.
- Temporarily commented out Forge in the installation `ui.View` during standard Setup to protect installation success until a dynamic API is finalized.

## File Usage Rules

1. Never import specific legacy functions from `config_generator.py` or `.utils` since they are deleted.
2. Configuration loading must use `config.load_bot_config()` or `config.load_user_config()`.

### TODOs Remaining

- Expand Forge API fetching in `mc_installer.py`
- Add full translation support (i18n) for discord bot replies
- Complete unit testing for `LogDispatcher` parsing mechanics
- Mascan-proof the offline mode whitelist system (implement secondary layer of UUID verification if proxy headers imply otherwise)
