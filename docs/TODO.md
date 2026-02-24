# Project Status & Roadmap

**Current Version**: `v2.5.4`
**Last Updated**: February 16, 2026

## ✅ Completed Features

- **Core**:
  - [x] Process Management (Start/Stop/Restart) via `subprocess`.
  - [x] RCON Communication (`src/utils.rcon_cmd`).
  - [x] Thread-safe Config System (`filelock`).
  - [x] Unified Installer (`install.bat` + `install.sh`).
  - [x] Docker WSL 2 Integration support.
  - [x] Progress tracking in all installers.
  - [x] Dynamic Minecraft version fetching with fallbacks.

- **Console & Logging**:
  - [x] Live Log Tailing (`aiofiles`).
  - [x] Discord Embed Output (Colored logs).
  - [x] Owner-only `/cmd` command.
  - [x] Unbuffered output for real-time progress.

- **Monitoring**:
  - [x] Hardware Info (CPU/RAM/Disk via `psutil`).
  - [x] Player Count Presence Status.

- **Stats**:
  - [x] Mojang API Lookup (Online/Premium).
  - [x] NBT Data Parsing (Offline/Cracked).

- **Backup**:
  - [x] World Zipping.
  - [x] Ephemeral Upload/Download (`pyonesend`).

- **Economy**:
  - [x] Balance System.
  - [x] Word Hunt Minigame.

- **AI**:
  - [x] Chat Integration (`xai-sdk`).
  - [x] Weekly MOTD Generation.

- **Automation**:
  - [x] Event Scheduling (`/event`).
  - [x] Regex Chat Triggers.

- **Installation & Setup**:
  - [x] Windows WSL 2 Bootstrap.
  - [x] Docker cache busting mechanism.
  - [x] Automatic error detection and recovery.
  - [x] Ghost Mode simulation for testing.
  - [x] Version 1.21.11 support (latest).

## 🚧 In Progress / Planned

### High Priority

- **Mod Management**:
  - [ ] Modrinth API Integration.
  - [ ] Auto-updating modpacks.
  - [ ] Per-user mod whitelist/blacklist.

- **playit.gg Integration**:
  - [ ] Add playit container to docker-compose.
  - [ ] Use: `network_mode: service:mc-bot`.
  - [ ] Tunnel port: 25565 (Minecraft).
  - [ ] Claim tunnel via https://playit.gg/claim link.
  - [ ] Remove public port 25565 if using playit only.
  - [ ] Test connection from external network.
  - [ ] Add Discord command to show playit IP.

### Medium Priority

- **Enhanced Monitoring**:
  - [ ] Server uptime statistics.
  - [ ] Player session tracking.
  - [ ] Performance metrics dashboard.

- **Backup Improvements**:
  - [ ] Scheduled automatic backups.
  - [ ] Backup versioning and retention.
  - [ ] Incremental backups.
  - [ ] Change py-onesend to transfer.sh

## Known Issues & Fixes (v2.5.4)

### Fixed in v2.5.4

- **Windows Docker WSL Integration**:
  - Fixed "docker not found in WSL" error by adding Docker Desktop checks.
  - Added explicit instructions for enabling WSL integration.
  - Enhanced `install.bat` to verify Docker before attempting WSL setup.

- **Installation Progress Tracking**:
  - Added numbered step indicators in all installers.
  - Unbuffered output (`PYTHONUNBUFFERED=1`) prevents hanging.
  - Real-time progress reporting during Docker build.

- **Minecraft Version Caching**:
  - Fixed hardcoded version 1.21.5 to 1.21.11 (actual latest).
  - Improved cache invalidation in docker-compose.yml.
  - Added CACHEBUST argument to Dockerfile.

- **Installation Hang After Credentials**:
  - Fixed by disabling stdout buffering in install.sh.
  - Added `set -e` for proper error handling.
  - Progress indicators prevent the appearance of hang.

## 🕒 Version History

- **v2.5.4** (Current): Stability & Windows Support. Docker WSL integration, progress tracking, version updates.
- **v2.5.3**: Cleanup Update. Root directory sanitization, Documentation split.
- **v2.5.2**: Automation Update. Events, MOTD, Triggers.
- **v2.5.0**: Advanced Features. Stats, Info, Backups, Economy.
- **v2.0.0**: Rewrite to discord.py 2.0.
- **v1.0.0**: Legacy Script.

## Maintenance Notes

### Docker Cache Management

When making changes to dependencies or code:

```bash
# Option 1: Use automatic cache busting (recommended)
CACHEBUST=$(date +%s) docker compose up -d --build

# Option 2: Clear all Docker caches and rebuild
docker buildx prune -af
docker compose up -d --build
```

### Testing Setup Wizard

For testing version resolution without a full installation:

```bash
python install/simulate.py
```

### Updating Minecraft Versions

To add new versions to the quick-select list:
1. Edit `src/setup_views.py` - Update `common_versions` list
2. Edit `src/version_fetcher.py` - Update fallback versions
3. Versions are auto-fetched from APIs on first use

### Troubleshooting Installation Issues

If installation fails:
1. Check Docker Desktop is running
2. Ensure WSL 2 integration is enabled
3. Review logs: `docker compose logs mc-bot`
4. Try cache busting: `CACHEBUST=$(date +%s) docker compose up -d --build`
