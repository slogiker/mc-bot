# Project Status & Roadmap

**Current Version**: `v2.5.3`

## ✅ Completed Features

- **Core**:
  - [x] Process Management (Start/Stop/Restart) via `subprocess`.
  - [x] RCON Communication (`src/utils.rcon_cmd`).
  - [x] Thread-safe Config System (`filelock`).
  - [x] Unified Installer (`install.py`).
- **Console & Logging**:
  - [x] Live Log Tailing (`aiofiles`).
  - [x] Discord Embed Output (Colored logs).
  - [x] Owner-only `/cmd` command.
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

## 🚧 In Progress / Planned

- **Mod Management**:
  - [ ] Modrinth API Integration.
  - [ ] Auto-updating modpacks.

- **Add playit.gg Docker tunnel**

- Add playit container to docker-compose
- Use: network_mode: service:mc-bot
- Tunnel port: 25565 (Minecraft)
- Claim tunnel via https://playit.gg/claim link
- Remove public port 25565 if using playit only
- Test connection from external network
- Add Discord command to show playit IP

## 🕒 Version History

- **v2.5.3**: Cleanup Update. Root directory sanitization, Documentation split, Emoji removal.
- **v2.5.2**: Automation Update. Events, MOTD, Triggers.
- **v2.5.0**: Advanced Features. Stats, Info, Backups, Economy.
- **v2.0.0**: Rewrite to discord.py 2.0.
- **v1.0.0**: Legacy Script.
