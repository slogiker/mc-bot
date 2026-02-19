\# MC-Bot Code Review \& Fix Prompt



You are a senior Python engineer working on a Discord bot that manages a Minecraft Java server. The project uses `discord.py`, Docker, tmux, RCON, and JSON config files. Your job is to fix all issues listed below, in order of severity.



---



\## CONTEXT



\- \*\*Bot entry point:\*\* `bot.py`

\- \*\*Cogs directory:\*\* `cogs/` (each file is a Discord command module)

\- \*\*Core logic:\*\* `src/` (config, server manager, utils, backup, etc.)

\- \*\*Config files:\*\* `data/bot\_config.json` (system state), `data/user\_config.json` (user preferences)

\- \*\*Deployment:\*\* Docker Compose, single container named `mc-bot`



---



\## 🔴 CRITICAL BUGS — Fix These First



\### 1. `cogs/backup.py` — Missing Imports (Will Crash on Load)

The entire cog is missing imports. Add the following at the top:

```python

import os

import asyncio

from src.config import config

from src.logger import logger

from src.backup\_manager import backup\_manager

```



\### 2. `admin.py` — Wrong Return Value Unpack

`backup\_manager.create\_backup()` returns \*\*3 values\*\* `(success, filename, filepath)` but `admin.py` unpacks only 2:

```python

\# WRONG — raises ValueError at runtime

success, result = await backup\_manager.create\_backup(...)



\# CORRECT

success, result, filepath = await backup\_manager.create\_backup(...)

```



\### 3. `src/mc\_manager.py` — References Non-Existent Attribute

`config.SIMULATION\_MODE` does not exist. The correct attribute is `config.dry\_run`:

```python

\# WRONG

if config.SIMULATION\_MODE:



\# CORRECT

if config.dry\_run:

```



\### 4. `src/config.py` — Missing `discord` Import in `resolve\_role\_permissions`

The method uses `discord.utils.get` but `discord` is never imported in `config.py`. Add:

```python

import discord

```



\### 5. `config.OWNER\_ID` — Never Defined

`OWNER\_ID` is referenced in `bot.py` and `cogs/console.py` but never set in the `Config` class. Add this to `Config.load()`:

```python

self.OWNER\_ID = bot\_cfg.get('owner\_id')

```



---



\## 🔴 CRITICAL SECURITY VULNERABILITIES — Fix Immediately



\### 6. `docker-compose.yml` — RCON Port Publicly Exposed

Port `25575` (RCON) must \*\*never\*\* be exposed externally. Anyone who finds the host IP can execute arbitrary server commands. Remove this line:

```yaml

\# DELETE THIS LINE

\- "25575:25575"

```



\### 7. `src/config.py` — Simulation Mode Resets on Every Config Save

`save\_bot\_config()` and `save\_user\_config()` both call `self.load()` at the end. `load()` hardcodes `self.dry\_run = False`, which silently disables simulation mode mid-run. Fix by preserving the flag across reloads:

```python

def load(self):

&nbsp;   \_dry\_run = getattr(self, 'dry\_run', False)  # Preserve existing value

&nbsp;   # ... rest of load logic ...

&nbsp;   self.dry\_run = \_dry\_run  # Restore after load

```



---



\## 🟠 SIGNIFICANT LOGIC BUGS



\### 8. `src/backup\_manager.py` — Wrong Backup Directory

The backup path resolves to `./mc-server/backups` but the Docker volume mounts `./backups:/app/backups`. These are different locations. Backups are lost on container restart. Fix the constructor:

```python

\# WRONG

self.backup\_dir = os.path.join(config.SERVER\_DIR, 'backups')



\# CORRECT

self.backup\_dir = '/app/backups'

```



\### 9. `cogs/automation.py` — Duplicate `except` Block (Dead Code)

The `scan\_logs\_for\_triggers` method has two identical `except Exception as e` blocks at the bottom. The first one is unreachable. Remove the duplicate.



\### 10. `cogs/automation.py` and `cogs/economy.py` — Inconsistent Permission Checks

`trigger\_add`, `trigger\_remove`, and `economy\_set` bypass the `has\_role()` decorator system and check `guild\_permissions.administrator` directly. Replace with:

```python

@has\_role("trigger\_add")  # or the relevant permission key

```



\### 11. `cogs/tasks.py` — Timezone Evaluated at Import Time

```python

\# This runs at import time, before bot is ready — crashes if timezone is invalid

@tasks.loop(time=dt\_time(22, 0, tzinfo=pytz.timezone(config.TIMEZONE)))

```

Move timezone resolution inside the task function body, or wrap it in a try/except with a UTC fallback.



---



\## 🟡 ARCHITECTURE PROBLEMS



\### 12. Multiple Cogs Spawning Duplicate `docker logs -f` Processes

`console.py`, `automation.py`, `economy.py`, and `admin.py` each independently spawn a `docker logs -f mc-bot` subprocess. You are attaching 4+ readers to the same container simultaneously. This causes duplicate log processing and wasted resources.



\*\*Solution:\*\* Create a single `src/log\_dispatcher.py` service that reads the log stream once and emits events via asyncio queues or callbacks. Cogs subscribe to specific event types (player join, chat message, etc.) instead of reading logs themselves.



\### 13. `src/config.py` — Full Reload on Every Config Save

`save\_bot\_config()` calls `self.load()`, which re-reads and re-validates \*\*both\*\* config files on every economy transaction, player join, and event creation. Extract the in-memory attribute update from the full disk reload.



\### 14. JSON Economy — Race Condition on Concurrent `/pay`

The current pattern is:

```python

config = load\_bot\_config()         # read

config\['economy']\[uid] += amount   # modify

save\_bot\_config(config)            # write

```

If two `/pay` commands run concurrently between read and write, one transaction is silently lost. Migrate economy data to \*\*SQLite via `aiosqlite`\*\* and use transactions:

```python

async with db.execute("UPDATE economy SET balance = balance + ? WHERE user\_id = ?", (amount, uid)):

&nbsp;   await db.commit()

```



\### 15. Duplicate Server Manager Instances

`bot.py` creates `self.server = TmuxServerManager()` and `src/mc\_manager.py` creates its own separate `mc\_manager = TmuxServerManager()` instance. They will diverge in state (one may think the server is running while the other does not). Pick one — use `bot.server` everywhere and delete the global instance in `mc\_manager.py`, or vice versa.



---



\## 🟡 CODE QUALITY FIXES



\### 16. `cogs/info.py` — Unused Imports

`display\_key` and `map\_key` are imported from `src/utils` but never used. Remove them.



\### 17. `src/server\_info\_manager.py` — Race Condition in `set\_spawn`

```python

\# load and save are not atomic — another coroutine can modify the file between these two calls

await asyncio.to\_thread(config.save\_bot\_config, config.load\_bot\_config() | updates)

```

Use the existing `FileLock` pattern properly, or add a dedicated async lock around load+modify+save sequences.



\### 18. `cogs/console.py` — Fragile Player Name Parsing

```python

player\_name = msg.split(" joined the game")\[0].strip()

```

This breaks if plugins or Paper prefix the message. Replace with regex:

```python

import re

match = re.match(r'^(\\w+) (?:joined|left) the game', msg)

if match:

&nbsp;   player\_name = match.group(1)

```



\### 19. `cogs/economy.py` — Convoluted Task Startup

`word\_hunt\_task` has a `pass` body and only exists to trigger `before\_word\_hunt`, which then calls `create\_task`. Simplify by starting the task directly in `cog\_load`:

```python

async def cog\_load(self):

&nbsp;   self.bot.loop.create\_task(self.random\_word\_hunt\_loop())

```

Remove `word\_hunt\_task` and `before\_word\_hunt` entirely.



---



\## 🗑️ REMOVE THESE



| File / Code | Reason |

|---|---|

| `src/config\_generator.py` | Generates old `config.json` format. Fully superseded. Dead code. |

| `bot\_config.json` (repo root) | Duplicate of `data/bot\_config.json`. Causes confusion. |

| `user\_config.json` (repo root) | Duplicate of `data/user\_config.json`. Causes confusion. |

| `utils/` folder | Contains only an empty `\_\_init\_\_.py`. Serves no purpose. |

| `--dry-run` argument in `bot.py` | Already marked deprecated in the code. Remove it and its handling. |

| `mc\_manager.py` global instance | Conflicts with `bot.server`. Keep one, remove the other. |



---



\## ✅ THINGS TO ADD



\### 1. SQLite for Economy and Events

Replace `bot\_config.json` economy and events storage with `aiosqlite`. Schema:

```sql

CREATE TABLE economy (user\_id TEXT PRIMARY KEY, balance INTEGER DEFAULT 0);

CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT, time TEXT, description TEXT, reminded\_1h INTEGER, reminded\_24h INTEGER);

```



\### 2. Docker Health Check

Add to `docker-compose.yml` so Docker knows the bot has actually connected:

```yaml

healthcheck:

&nbsp; test: \["CMD", "python", "-c", "import os; exit(0 if os.path.exists('/tmp/bot\_ready') else 1)"]

&nbsp; interval: 30s

&nbsp; timeout: 10s

&nbsp; retries: 3

```

Write `/tmp/bot\_ready` inside `on\_ready()`.



\### 3. Central Log Dispatcher Service

```python

\# src/log\_dispatcher.py

class LogDispatcher:

&nbsp;   def \_\_init\_\_(self):

&nbsp;       self.\_subscribers: dict\[str, list\[asyncio.Queue]] = {}



&nbsp;   def subscribe(self, event\_type: str) -> asyncio.Queue:

&nbsp;       q = asyncio.Queue()

&nbsp;       self.\_subscribers.setdefault(event\_type, \[]).append(q)

&nbsp;       return q



&nbsp;   async def start(self):

&nbsp;       # Single docker logs -f process

&nbsp;       # Parse lines and emit to subscriber queues by event type

```



\### 4. Proper `OWNER\_ID` Population During Setup

In `setup\_helper.py`, after setup completes, resolve and save the owner's Discord ID to `bot\_config.json`:

```python

bot\_cfg = config.load\_bot\_config()

bot\_cfg\['owner\_id'] = guild.owner\_id

config.save\_bot\_config(bot\_cfg)

```



\### 5. Command Audit Logging for `/cmd`

Even though `/cmd` is owner-only, log every execution:

```python

logger.info(f"CMD executed by {interaction.user} ({interaction.user.id}): {command}")

```



---



\## PRIORITY ORDER FOR FIXES



1\. Fix all 🔴 Critical Bugs (items 1–5) — bot won't run without these

2\. Fix all 🔴 Security issues (items 6–7) — do not deploy without these

3\. Fix the backup directory (item 8) — you are silently losing all backups right now

4\. Fix the duplicate log readers (item 12) — causes incorrect behavior at runtime

5\. Fix the economy race condition (item 14) — causes silent data loss

6\. Fix remaining 🟠 and 🟡 items

7\. Implement additions



Do not add new features until all 🔴 and 🟠 items are resolved.

