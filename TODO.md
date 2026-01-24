# MC-Bot TODO List

## ✅ Recently Completed (2026-01-24)

### Security Fixes
- [x] **Command injection vulnerability** - Added `shlex.quote()` to prevent shell injection through config values
- [x] **Fixed .gitignore** - Prevent secrets from being committed (config.json, .env, etc.)
- [x] **Removed RCON port exposure** - Port 25575 no longer exposed in Docker
- [x] **Auto-config generation** - Bot creates config.json with intelligent defaults

### Performance Fixes
- [x] **Async I/O migration** - Converted `utils.py`, `admin.py`, `stats.py` to non-blocking async operations
- [x] **Race condition locks** - Added asyncio.Lock to prevent duplicate syncs and state corruption

### Code Quality
- [x] **Unified dry-run mode** - Removed TEST_MODE, consolidated to single `--dry-run` flag
- [x] **Better error messages** - Management commands now show helpful error feedback
- [x] **Fixed bare except clauses** - Replaced with specific exception types in stats.py

---

## 🔴 Critical Bugs (Fix ASAP)

### BUG: Log Monitor Reset
**File:** `cogs/tasks.py`  
**Severity:** HIGH  
**Impact:** Duplicate chat messages spam Discord after log rotation

**Problem:** When server rotates logs, monitor resets position to 0 and re-reads entire log file, causing old messages to be resent.

**Fix:**
```python
# Line ~85 in tasks.py
if current_size < self.log_position:
    # Log rotated
    self.log_position = current_size  # NOT 0!
    return  # Stop processing this cycle
```

---

### BUG: Blocking I/O in info.py
**File:** `cogs/info.py`  
**Severity:** MEDIUM  
**Impact:** Bot freezes during /version and /server_info commands

**Commands affected:**
- `/version` - Reads version files synchronously
- `/server_info` - Reads server.properties synchronously

**Fix:** Convert to async using `aiofiles` and `asyncio.to_thread`:
```python
import aiofiles

# Before:
with open(version_file, 'r') as f:
    version = f.read()

# After:
async with aiofiles.open(version_file, 'r') as f:
    version = await f.read()
```

---

### BUG: Inefficient Backup System
**File:** `src/backup_manager.py`  
**Severity:** MEDIUM  
**Impact:** Creates temporary copy of world before zipping (doubles disk usage)

**Problem:**
```python
# Current approach:
shutil.copytree(world_path, temp_world)  # Copies entire world
shutil.make_archive(backup_path, 'zip', temp_world)  # Then zips the copy
shutil.rmtree(temp_world)  # Deletes temp copy
```

**Better approach:** Zip directly without temp copy:
```python
import zipfile
import os

with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(world_path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, world_path)
            zipf.write(file_path, arcname)
```

---

### BUG: Missing os.path Async Wrapping
**Files:** Multiple  
**Severity:** LOW-MEDIUM  
**Impact:** Blocking I/O calls throughout codebase

**Audit needed for:**
- `os.path.exists()` - Wrap in `await asyncio.to_thread()`
- `os.path.getsize()` - Wrap in `await asyncio.to_thread()`
- `os.listdir()` - Wrap in `await asyncio.to_thread()`
- `os.makedirs()` - Wrap in `await asyncio.to_thread()`

**Search command:**
```bash
grep -rn "os\.path\." --include="*.py" .
```

---

## 🟡 High Priority Improvements

### 1. Add Rate Limiting
**Priority:** HIGH  
**Files:** All command cogs

**Why:** Prevent command spam and DoS attempts

**Implementation:**
```python
from discord import app_commands

@app_commands.command()
@app_commands.checks.cooldown(1, 30)  # 1 use per 30 seconds
async def start(self, interaction):
    # ...
```

**Recommended limits:**
- `/start`, `/stop` - 1 per 30s
- `/restart` - 1 per 60s
- `/backup_now` - 1 per 5min
- `/cmd` - 5 per 60s
- `/stats`, `/status` - Use existing cooldowns

---

### 2. Add Type Hints
**Priority:** MEDIUM  
**Files:** All Python files

**Why:** Better IDE support, catch bugs early, improve maintainability

**Example:**
```python
from typing import Optional, Tuple

async def start(self) -> Tuple[bool, str]:
    """Start the Minecraft server"""
    # ...
```

**Use mypy for validation:**
```bash
pip install mypy
mypy src/ cogs/
```

---

### 3. Graceful Shutdown
**Priority:** MEDIUM  
**File:** `bot.py`

**Why:** Currently Ctrl+C or Docker stop leaves orphaned processes

**Implementation:**
```python
import signal

async def shutdown(bot):
    """Graceful shutdown handler"""
    logger.info("Shutdown initiated...")
    
    # Stop server if running
    if bot.server.is_running():
        await bot.server.stop()
    
    # Close bot connection
    await bot.close()
    
    logger.info("Shutdown complete")

def signal_handler(sig, frame):
    """Handle SIGINT and SIGTERM"""
    asyncio.create_task(shutdown(bot))

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

---

### 4. Better Config Validation
**Priority:** MEDIUM  
**File:** `src/config.py`

**Why:** Invalid config causes cryptic errors

**Use Pydantic for schema validation:**
```python
from pydantic import BaseModel, validator

class BotConfig(BaseModel):
    rcon_host: str
    rcon_port: int
    server_directory: str
    
    @validator('rcon_port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be 1-65535")
        return v
```

---

### 5. Add Logging Levels
**Priority:** LOW  
**File:** `bot.py`

**Add debug mode:**
```python
parser.add_argument("--debug", action="store_true")
if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)
```

---

## 🟢 Feature Requests (Future)

### 1. Playit.gg Integration
**Priority:** LOW  
**Description:** Free secure tunnel for public server access

**Implementation:**
- Install playit.gg agent in Docker container
- Auto-configure tunnel on server start
- Display public URL in Discord embed

---

### 2. Mod Management System
**Priority:** LOW  
**Description:** Interactive mod installation with dependency resolution

**Features:**
- Search mods via API (Modrinth, CurseForge)
- Auto-install dependencies
- Version compatibility checking
- Support for Paper, Fabric, Forge

**UI Flow:**
```
/install_mods
→ Select platform (Paper/Fabric/Forge)
→ Enter mod names (type 0 to finish)
→ Bot searches APIs
→ Shows results, asks for confirmation
→ Downloads and installs mods
→ Validates dependencies
```

---

### 3. Vanilla Tweaks Integration
**Priority:** LOW  
**Description:** Allow users to upload Vanilla Tweaks datapacks

**Implementation:**
```python
@app_commands.command()
async def install_datapack(self, interaction, attachment: discord.Attachment):
    # Download zip
    # Validate structure
    # Extract to world/datapacks/
    # Reload datapacks via RCON
```

---

### 4. Version Selection
**Priority:** LOW  
**Description:** Dropdown menu to select Minecraft version

**Implementation:**
- Fetch versions from Minecraft version manifest
- Create autocomplete dropdown
- Download selected version JAR
- Update config automatically

---

### 5. Auto RAM Allocation
**Priority:** MEDIUM (Partially Completed)  
**Status:** ✅ Already implemented in `config_generator.py`

**Current behavior:**
- 16+ GB RAM → 4G-6G
- 8-16 GB RAM → 2G-4G
- 4-8 GB RAM → 1G-2G
- <4 GB RAM → 512M-1G

**Potential improvement:** Make it adjustable in settings

---

### 6. Settings UI Consolidation
**Priority:** LOW  
**Description:** Single settings form instead of multiple commands

**Proposed UI:**
```
/settings
→ Shows modal with all config options
→ One "Save" button at bottom
→ Validates all fields
→ Updates config.json and reloads
```

---

### 7. Automatic Channel Creation
**Priority:** LOW (Partially Completed)  
**Status:** ✅ Already implemented in `setup_helper.py`

**Currently auto-creates:**
- "Minecraft Server" category
- command, log, debug channels
- MC Admin and MC Player roles

**Potential additions:**
- Server info channel (IP, version, seed, spawn)
- Make channel creation more configurable

---

## 📊 Code Quality Improvements

### Extract Duplicate Code
**Priority:** LOW  
**Files:** Multiple

**Examples:**
- Version parsing logic (appears in multiple places)
- Embed creation patterns
- Error handling patterns

**Create utilities:**
```python
# src/embed_utils.py
def create_success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=0x57F287)

def create_error_embed(title: str, error: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=f"**Error:** {error}",
        color=0xED4245
    )
```

---

### Add Unit Tests
**Priority:** LOW  
**Framework:** pytest

**Test coverage needed:**
- Config loading/validation
- Server manager start/stop
- Backup manager
- Utils functions

```bash
pip install pytest pytest-asyncio
pytest tests/
```

---

### Documentation
**Priority:** LOW  

**Create:**
- `docs/ARCHITECTURE.md` - System design overview
- `docs/TROUBLESHOOTING.md` - Common issues and solutions
- `docs/CONTRIBUTING.md` - Development guidelines
- Add docstrings to all public functions

---

## 🎯 Priority Order

**Week 1 (Critical):**
1. Fix log monitor reset bug
2. Fix blocking I/O in info.py
3. Add rate limiting to commands

**Week 2 (Important):**
4. Optimize backup system (remove temp copy)
5. Add type hints to main modules
6. Audit remaining os.path blocking calls

**Week 3 (Quality):**
7. Add graceful shutdown
8. Better config validation with Pydantic
9. Extract duplicate code

**Future (When ready):**
10. Mod management system
11. Playit.gg integration
12. Settings UI consolidation
13. Unit tests and documentation

