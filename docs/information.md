# MC-Bot — Complete Developer Reference
**Version:** v2.8.0-dev
**Last Updated:** March 2026

[PROJECT OVERVIEW]
Purpose — Self-hosted Discord bot managing a Minecraft Java server inside Docker via tmux and RCON.
Key components — Python 3.11, Docker, Java 21, tmux, RCON, Playit.gg.
Design — Single container for bot and MC server; split config for machine state vs. user preferences.
Log Flow — Centralized LogDispatcher fans out docker logs to subscribers (console, automation, watcher).
Presence — Bot status reflects Docker/Minecraft process state (Online, Idle, Offline).

[ARCHITECTURE DEEP DIVE]
Startup — bot.py initializes ServerManager, JoinGuard, LogWatcher; setup_hook loads cogs; on_ready syncs guild.
Log Dispatcher — Singleton spawning one `docker logs -f` process; broadcasts to asyncio.Queue subscribers.
Manager Hierarchy — ServerInterface ABC implemented by TmuxServerManager (prod) and MockServerManager (test).
Permissions — Role-name based mapping in user_config.json; resolved to IDs at runtime via config.ROLES.
Control Panel — Sticky interactive embed in command channel; refreshed via background task.

[CONFIGURATION SYSTEM]
Environment — BOT_TOKEN, RCON_PASSWORD, RCON_HOST (defaults to 127.0.0.1).
bot_config.json — Machine state (Channel/Role IDs, spawn coords, online player list, economy).
user_config.json — User preferences (RAM, schedules, timezone, role permissions, log triggers).
Config Class — Singleton with FileLock protection; handles dynamic updates and role resolution.
Validation — RAM format (digit+G/M), HH:MM time strings, and pytz timezone strings enforced on load.
World Folder — config.WORLD_FOLDER property dynamically reads `level-name` from server.properties.

[SERVER CONTROL COMMANDS]
/start — Starts MC server in tmux (30s cooldown).
/stop — Sends RCON stop, clears online player list, kills tmux if needed (30s cooldown).
/restart — Graceful stop, clears online player list, followed by start (60s cooldown).
/control — Spawns interactive ControlView buttons.
/bot_restart — Exits bot process for Docker container restart.
/cmd <command> — Owner-only raw RCON execution.

[SERVER INFORMATION COMMANDS]
/status — Online/Offline status and player list embed (deferred).
/players — Lists online players via RCON (deferred).
/version — Parses version string from latest.log.
/seed — Reads seed via server.properties or RCON (deferred).
/info — Full system metrics, IP, version, and uptime embed (deferred).
/ip — Fetches public Playit.gg address (2-hour cache).
/set_spawn — Saves coordinates to bot_config.json (Admin only, deferred).

[ADMINISTRATION COMMANDS]
/setup — Interactive 7-step server installation wizard.
/sync — Re-syncs slash commands to the guild.
/settings — GUI for modifying RAM, schedules, and permissions.
/backup_now — Triggers immediate manual backup.
/logs — Shows tail of docker logs in Discord.
/whitelist_add — RCON whitelist management.

[BACKUP]
Purpose — Manages world backups with automated retention and direct Discord downloads.
Key files — cogs/backup.py (Discord commands), src/backup_manager.py (Zipping logic).
Config — backup_time (HH:MM), backup_keep_days (int), COMMAND_CHANNEL_ID.
Permissions — /backup, /backup_list, and /backup_download require Administrator permission.
Failure modes — Disk space exhaustion, Discord attachment size limit (>25MB).
Dependencies — Called by BackupCog, calls BackupManager.
Notes — Auto backups (scheduled) have retention applied; custom backups are kept indefinitely.

[JOINGUARD]
Purpose — Prevents impersonation on offline-mode servers via Discord linking and challenges.
Key files — src/join_guard.py (Core logic), src/mc_link_manager.py (Link storage).
Codes — Issues 6-char alphanumeric verification codes (e.g., A7B9X2).
Grace Period — 1800s (30 mins) window for re-joins after logout.
Challenge — 300s (5 mins) expiry for DM challenges.
Fallback — Challenges fallback to the command channel if user DMs are disabled.
Notes — Premium accounts are auto-verified (no Discord required if unlinked).

[COGS: CORE]
admin.py — Slash command syncing, raw logs, whitelist management.
automation.py — Regex chat triggers (deferred add/remove) and MOTD generation.
console.py — Log batching (0.5s), join/leave/death event detection.
help.py — Dynamic help embed filtered by user permissions.
info.py — System metrics (psutil) and Vanilla TPS fallback monitor.
management.py — Server lifecycle control (start/stop/restart) with player list cleanup.

[COGS: UTILITY]
link.py — Discord account linking for offline-mode protection.
playit.py — Playit.gg API client for public IP retrieval.
settings.py — Modal-based GUI for runtime configuration updates.
setup.py — Install wizard entry point and reinstall logic.
stats.py — Player statistics via Mojang API and NBT parsing (uses config.WORLD_FOLDER).
tasks.py — Crash detection (30s) and Playit agent watchdog.

[SRC: CORE MODULES]
backup_manager.py — Async world zipping and retention cleanup.
config.py — Thread-safe config singleton with JSON validation and dynamic world-folder detection.
log_dispatcher.py — Centralized `tail -F` stream fan-out.
mc_installer.py — Platform-specific JAR downloads and EULA handling.
mc_link_manager.py — Async CRUD for Discord-MC account mappings.
mojang.py — Mojang API client for premium status verification.

[SRC: UTILITY MODULES]
server_tmux.py — Tmux-based process control and uptime tracking.
setup_views.py — Multi-step Discord UI for server installation.
utils.py — RCON client, role checks, and UUID resolution.
log_watcher.py — LogDispatcher subscriber emitting login events.
version_fetcher.py — Cached Modrinth/Mojang version metadata.
server_info_manager.py — Persistent #server-information channel manager.

[KNOWN BUGS: RESOLVED]
Security — RCON port isolated to localhost; Administrator-only backup commands.
Concurrency — FileLock applied to all JSON writes; economy race conditions fixed.
Logic — Backup directory absolute pathing; world existence check before zipping.
Architecture — Duplicate log/server managers consolidated to singletons.
Performance — Added defer() to long-running RCON and I/O commands to prevent timeouts.
JoinGuard — Switched to 6-char alphanumeric codes and 30-minute grace window.

[OPEN ISSUES]
Plugin Selection — Modrinth slugs in setup modal lack autocomplete validation.
Docker Build — Container image layers need optimization for faster rebuilds.
Discord Limits — Large backup files (>25MB) cannot be sent via Discord attachment.
RCON Timing — Intermittent connection refused during the first 60s of server boot.

[VERSION HISTORY]
v2.8.2 — Rewrite of Playit claim flow for CLI v0.17 compatibility.
v2.8.1 — JoinGuard DM fallback; Setup wizard timeout messaging.
v2.8.0-dev — Player linking system; Server uptime tracking; Vanilla TPS fallback.
v2.7.2 — Zero-emoji setup UI; RCON synchronization hardening.
v2.7.1 — Playit crash recovery; Docker-based pytest suite integration.
v2.6.0 — 28-issue hardening pass; bot_config volume persistence fix.

[ROADMAP]
High — Migrate JSON storage (economy/events) to SQLite via aiosqlite.
High — Implement Minecraft-to-Discord chat bridge via log streaming.
Medium — Windows native installer (install.ps1) with WSL automation.
Medium — Performance dashboard showing TPS and player count trends.
Low — Death counter leaderboard and automated allowlist request system.
