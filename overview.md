# MC-Bot — Current Issues Overview

> Generated from senior code review · February 2026

---

## 🔴 Critical — Will Crash in Production

### 1. Wrong Tuple Unpacking in `cogs/tasks.py`
`backup_manager.create_backup()` returns **3 values** `(success, filename, filepath)` but `daily_backup` only unpacks **2**.

```python
# ❌ CURRENT — crashes with ValueError
success, result = await backup_manager.create_backup()

# ✅ FIX
success, filename, filepath = await backup_manager.create_backup()
```

---

### 2. Missing `import asyncio` in `src/setup_views.py`
`asyncio` is only imported *locally* inside `_start_installation()`, making it unavailable in `_save_config_to_file()`.

```python
# ❌ CURRENT — NameError at runtime
async def _save_config_to_file(self, updates: dict):
    await asyncio.to_thread(...)  # asyncio not in scope here

# ✅ FIX — add to top of file
import asyncio
```

---

### 3. Attribute Name Mismatch in `cogs/automation.py`
`__init__` sets `self.log_scan_task = None`, but `cog_load` assigns `self.log_task`. `cog_unload` then references `self.log_task` which doesn't exist if the cog unloads before loading — raises `AttributeError`.

```python
# ❌ CURRENT — three different names for the same thing
self.log_scan_task = None   # __init__
self.log_task = asyncio.create_task(...)  # cog_load
if self.log_task: ...        # cog_unload

# ✅ FIX — use one consistent name, init in __init__
def __init__(self, bot):
    self.log_task = None  # consistent throughout
```

---

## 🟠 Significant — Bad Behaviour or Resource Leaks

### 4. Empty `word_hunt_task` Loop in `cogs/economy.py`
The `@tasks.loop(minutes=45)` loop body is `pass` — it does nothing. The real loop is spawned separately in `before_loop`. The task wastes a heartbeat every 45 minutes for no reason.

```python
# ❌ CURRENT — pointless loop
@tasks.loop(minutes=45)
async def word_hunt_task(self):
    pass

# ✅ FIX — spawn directly in cog_load, remove the task entirely
async def cog_load(self):
    self.hunt_task = asyncio.create_task(self.random_word_hunt_loop())
```

---

### 5. Queue Memory Leak in `src/log_dispatcher.py`
`automation.py` subscribes to `log_dispatcher` but **never unsubscribes** on cog unload. Dead queues accumulate and keep receiving data forever.

```python
# ✅ FIX — add to automation.py cog_unload
def cog_unload(self):
    self.motd_loop.cancel()
    if self.log_task:
        self.stop_scan.set()
        self.log_task.cancel()
    if hasattr(self, 'log_queue'):
        from src.log_dispatcher import log_dispatcher
        log_dispatcher.unsubscribe(self.log_queue)
```

---

### 6. No Timeout on External HTTP Requests in `cogs/stats.py`
If Mojang's API goes down, `get_uuid_online()` hangs indefinitely — blocking the entire async event loop for that interaction.

```python
# ❌ CURRENT — no timeout
async with aiohttp.ClientSession() as session:
    async with session.get(f'https://api.mojang.com/...') as resp:

# ✅ FIX
timeout = aiohttp.ClientTimeout(total=5)
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.get(f'https://api.mojang.com/...') as resp:
```

---

### 7. Inconsistent `GUILD_ID` Type in `src/config.py`
`setup_helper.py` stores `guild_id` as a **string** (`str(guild.id)`), but other places call `int(config.GUILD_ID)` without a null check, which crashes if the value is `None`.

```python
# ❌ CURRENT — setup_helper stores string
updates['guild_id'] = str(guild.id)

# ❌ CURRENT — bot.py calls int() without null guard in some paths
guild = self.get_guild(int(config.GUILD_ID))

# ✅ FIX — store as int, always guard against None
updates['guild_id'] = guild.id  # store as int

if config.GUILD_ID:
    guild = self.get_guild(int(config.GUILD_ID))
```

---

## 🟡 Code Quality — Low Risk but Should Be Fixed

### 8. Duplicate Import in `cogs/console.py`
```python
from datetime import datetime  # line 6
from datetime import datetime  # line 7 — exact duplicate, remove one
```

### 9. Deprecated API in `cogs/console.py`
```python
# ❌ Deprecated in Python 3.10+
last_send = asyncio.get_event_loop().time()

# ✅ Use instead
last_send = asyncio.get_running_loop().time()
```

### 10. Conflicting RCON Libraries in `requirements.txt`
Both `aio-mc-rcon` and `mcrcon` are listed. Only `aiomcrcon` is actually imported in `utils.py`. `mcrcon` is dead weight.

```
# ✅ Remove this line from requirements.txt
mcrcon
```

### 11. Typo in `cogs/ai.py` Error Message
```python
# ❌ "efficient" makes no sense here
"❌ AI features are not enabled. efficient API key or SDK missing."

# ✅ Should be
"❌ AI features are not enabled. No valid API key or SDK found."
```

### 12. Leading Whitespace on Line 1 of `src/server_info_manager.py`
The file starts with 4 spaces before the first import. Cosmetic but flagged by every linter.

### 13. Hardcoded Command Names in `cogs/help.py`
The `categories` dictionary hardcodes command names as strings. Adding a new command to a cog requires a manual update here or it won't appear in `/help`.

```python
# Consider building this dynamically from bot.tree.get_commands()
# or adding a category attribute to each command
```

---

## 📋 Summary

| Severity | Count | Fix Time (est.) |
|---|---|---|
| 🔴 Critical | 3 | ~30 minutes |
| 🟠 Significant | 4 | ~1 hour |
| 🟡 Code Quality | 6 | ~45 minutes |
| **Total** | **13** | **~2.5 hours** |

### Fix Priority for Demo Day
1. **`cogs/tasks.py`** — tuple unpack crash (2 min fix)
2. **`src/setup_views.py`** — missing import (1 min fix)
3. **`cogs/automation.py`** — attribute name mismatch (5 min fix)

Fix those three and the bot won't hard-crash during a live demo.
