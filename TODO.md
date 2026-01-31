# MC-Bot TODO

## 🎯 Current Focus

### Next Up (Week 2)
- [ ] **Add type hints** to main modules (`src/`, `cogs/`) - Better IDE support, catch bugs early
- [ ] **Better config validation** with Pydantic - Prevent cryptic errors from invalid config

### Later (Week 3+)
- [ ] **Logging levels** - Add `--debug` flag for detailed logging
- [ ] **Extract duplicate code** - Create embed utility functions, consolidate patterns
- [ ] **Unit tests** - Add pytest for critical components

---

## 🚀 Feature Ideas

### High Priority
- [ ] **Mod Management** - Interactive mod installation with dependency resolution (Modrinth/CurseForge)
- [ ] **Playit.gg Integration** - Free secure tunnel for public server access
- [ ] **Vanilla Tweaks** - Allow datapack uploads via Discord

### Low Priority
- [ ] **Version Selector** - Dropdown to select/download MC versions
- [ ] **Settings UI** - Single modal instead of multiple commands
- [ ] **Auto RAM Allocation** - Make adjustable in settings (currently hardcoded)

---

## ✅ Completed (2026-01-31)

### Major Fixes
| Item | Status |
|------|--------|
| Log monitor reset bug | ✅ Fixed duplicate messages after rotation |
| Blocking I/O (info.py) | ✅ Converted to async (version, mods, server_info) |
| Inefficient backups | ✅ Direct zip (~50% disk savings) |
| Async wrapping | ✅ All critical paths now async |
| Rate limiting | ✅ 5 commands protected |
| Graceful shutdown | ✅ Clean stop on Ctrl+C |
| Code dedup | ✅ Removed 36 duplicate lines |

### Week Status
- ✅ **Week 1** (Critical) - 100% Complete
- 🚧 **Week 2** (Important) - 67% Complete  
- 🚧 **Week 3** (Quality) - 67% Complete

<details>
<summary>📋 View Detailed Archive</summary>

## Archive: Completed Items

### 2026-01-31 Afternoon
- **Backup optimization** - Removed temp world copy, saves ~50% disk space
- **Async I/O completion** - Wrapped os.listdir, os.path.getmtime, os.remove in backup_manager.py and bot.py
- **Rate limiting** - Added cooldowns: /start, /stop (30s), /restart (60s), /backup_now (5min), /cmd (5/min)
- **Graceful shutdown** - Signal handlers for SIGINT/SIGTERM, clean server stop

### 2026-01-31 Morning
- **Log monitor reset** - Fixed duplicate chat spam after log rotation in tasks.py
- **Blocking I/O (info.py)** - Async version/mods/server_info, created parse_server_version() utility
- **Async wrapping** - Fixed os.path calls in tasks.py, info.py, utils.py

### 2026-01-24
- **Security** - Command injection fix, .gitignore secrets, removed RCON exposure
- **Performance** - Async I/O in utils.py, admin.py, stats.py; race condition locks
- **Code quality** - Unified dry-run mode, better error messages, fixed bare except

</details>

---

## 📝 Notes

**Startup/Setup Code** (Not critical for async):
- `src/config.py` - Runs once at startup
- `src/mc_installer.py` - Setup script only
- `src/config_generator.py` - Config generation
- `src/logger.py` - Background logging

**All critical async paths are now non-blocking!** ✅
