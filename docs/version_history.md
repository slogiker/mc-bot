# MC-Bot Version History

This document chronicles the evolution of the MC-Bot project, detailing major features, bug fixes, and architectural shifts across versions.

---

### v3.1.2 — Startup Hardening & UI Polish (Current)

**Key Features & Adjustments:**
- **Smart Bounded Restarts:** Replaced the aggressive restart loop with a smart, log-analyzing 3-attempt limit. It now reads `latest.log` to identify root causes (Java version, OOM, Port in use) before blindly restarting, sending detailed debug alerts if it fails completely.
- **Self-Healing World Generation:** If `server.jar` exists but the `world` folder is missing, the `start()` method now actively monitors the background Java process's terminal output for the `"Done"` string, safely auto-generating the files without arbitrary timeouts (crucial for slow hardware like Raspberry Pi CM4).
- **RCON Recovery:** Fixed a major bug in `src/rcon_manager.py` where a failed initial connection attempt (while the server was still booting) would cache a broken client state, permanently preventing RCON usage and causing false offline statuses.
- **Ultra-Simplified `/status` UI:** Reverted the status embed to an ultra-minimalistic design containing only the server state with dynamic colors (🟢 Online, 🟡 Stopped, 🔴 Offline/Crashed) based on user preference.
- **`install.sh` Overhaul:** Merged legacy `mc-bot.sh` commands into the main `install.sh` script, adding subcommands (`start`, `stop`, `restart`, `logs`, `update`, `reinstall`).
- **Comprehensive Reinstall Logic:** Added `install.sh reinstall` to easily clear credentials, wipe worlds, and create automatic emergency backups (`backup-final-<date>.zip`).
- **Docker Log Rotation:** Applied a `50m` max size and `3` max files limit in `docker-compose.yml` to prevent long-term disk space exhaustion.
- **Playit Flow Fixes:** Automated the `/playit claim` process. The bot now waits in the background and verifies the claim automatically. Fixed a critical HTTP header injection crash by rigorously sanitizing the secret key file.

### v3.1.1 — Observability & Post-Release Polish

**Key Features:**
- System Online notification sent to the command channel after startup.
- Minor bug fixes following the v3.1 release.

### v3.1.0 — Architecture Consolidation

**Key Features:**
- Merged feature branches into main.
- Centralized read-write concurrency via `FileLock`.
- Replaced classic `@commands.command` with full `/` app slash commands.
- Enhanced Ghost mode `--simulate` parameters.

### v3.0.0 — UUID Sessions & Windows Support

**Key Features:**
- **UUID Sessions:** Implemented secure offline-mode protection via a production-ready `/verify` command.
- **WSL2 Installer:** Production-ready Windows setup via dedicated Ubuntu distro natively in `install.ps1`.
- **Fail-Closed Mojang API:** Hardened security during Mojang outages to prevent bypassing the verification system.

### v2.8.3 — Permission & Installer Hardening

**Fixes:**
- **Permission Error:** Added `user: "1000:1000"` to `docker-compose.yml` to resolve UID mismatch on volume-mounted directories.
- **Playit Claim Flow:** Added a health-check wait loop in `install.sh` to ensure the container is fully running before attempting to generate a claim code.

### v2.8.2 — Playit Claim Flow Rewrite

**Fixes:**
- Replaced the entire tmux-polling claim flow with the scriptable CLI, extracting the public address directly without polling or timeouts.

### v2.8.1 — Bug Fix & Hardening Pass

**Fixes:**
- **Join Guard:** `_issue_challenge()` now catches `discord.Forbidden` separately from generic exceptions. When a player's Discord DMs are disabled, the verification embed is posted in the command channel as a public mention.
- **Setup Wizard Timeout:** Added timeout handling to `SetupView` to clearly indicate when the setup process has stalled.
- **Backup Downloads:** Replaced transfer.sh with direct Discord attachments for backup downloads.

### v2.8.0-dev — Security, Uptime & Code Hardening

**Key Features:**
- **Player Linking System:** Added `cogs/link.py` and `src/mc_link_manager.py` for offline-mode impersonation protection.
- **Server Uptime Statistics:** `server_tmux.py` persists start time, allowing `/info` to display human-readable uptime.
- **Vanilla TPS Fallback:** Added `/debug start` and `/debug stop` RCON method for non-Paper servers.
- **Real World Seed Display:** `/info` reads the actual seed via RCON when the server is online; falls back to `level.dat` parsing when offline.

### Pre-v2.8 (Legacy)

- **v2.7.2:** Setup UX Improvements, Emoji-less UI, 60s RCON polling during installation.
- **v2.7.1:** Playit Reliability, 2-hour cache TTL for `/ip`, Docker-based test suite.
- **v2.6.0:** Bug Fix & Hardening Release (28-issue comprehensive review).
- **v2.5.5:** Core Capabilities & Control Panel Update (Sticky `#command` UI, dynamic integrations).
- **v2.5.2:** Automation Update (Weekly MOTD, Regex chat triggers).
- **v2.0.0:** Migrated to discord.py v2.0 (Slash commands, Ghost mode).