# MC-Bot TODO

## 🎯 Current Focus


### High Priority
- [ ] **Full support for Windows without Docker** - Native Windows installation script (no Docker Desktop required)
- [ ] **Mod Management** - Interactive mod installation with dependency resolution (Modrinth/CurseForge)
- [ ] **Playit.gg Integration** - Free secure tunnel for public server access
- [ ] **Vanilla Tweaks** - Allow datapack uploads via Discord

### Low Priority
- [x] **Version Selector** - Dropdown to select/download MC versions
- [x] **Settings UI** - Single modal instead of multiple commands
- [?] **Auto RAM Allocation** - Make adjustable in settings (currently hardcoded)

---

## ✅ Completed (2026-02-01)

### Major Improvements
| Item | Status |
|------|--------|
| **Server Installation** | ✅ Non-blocking background task with progress monitoring |
| **Server Info** | ✅ Auto-updating `#server-information` channel |
| **Commands** | ✅ Cleaned up unused commands, categorized `/help` |
| **Status** | ✅ Fixed `/status`, added bot activity presence |
| **Docker** | ✅ Fixed code caching issues |
| Log monitor reset bug | ✅ Fixed duplicate messages after rotation |
| Blocking I/O | ✅ Converted to async (version, mods, server_info) |
| Inefficient backups | ✅ Direct zip (~50% disk savings) |

### Recent Updates
- **Interactive Setup**: Now supports overwriting existing installations with a safety warning.
- **Server Info Channel**: Automatically displays IP, Version, Seed, Spawn (configurable via `/set_spawn`).
- **Bot Status**: Shows "Minecraft Server: Online" or "Stopping..." in Discord member list.
- **Cleanup**: Removed redundant commands like `/force_restart` and `/bot_stop` to simplify usage.
---

## 📝 Notes

**Startup/Setup Code** (Not critical for async):
- `src/config.py` - Runs once at startup
- `src/mc_installer.py` - Setup script only
- `src/config_generator.py` - Config generation
- `src/logger.py` - Background logging

**All critical async paths are now non-blocking!** ✅
