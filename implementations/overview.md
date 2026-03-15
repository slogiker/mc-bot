# mc-bot — bugs & silent failures

---

This file is a collection of bugs and silent failures that I found in the mc-bot codebase. It is mostly a complete list of all bugs and silent failures.

## CRITICAL — will crash immediately when hit

### 1. `cogs/automation.py` — `AttributeError` on cog load
```python
def __init__(self, bot):
    self.motd_loop.start()  # motd_loop method does not exist in the file
```
The entire `automation` cog fails to load silently. `/trigger_add`, `/trigger_list`, `/trigger_remove`, and the log trigger scanner **never work**. No error shown to the user.

**Fix:** Either define `motd_loop` as a stub `@tasks.loop` or remove the `.start()` call until it's implemented.

---

### 2. `src/setup_views.py` — `AttributeError` when plugins are specified during `/setup`
```python
project = await updater.client.get_project(slug)
```
`ModUpdater` has no `.client` attribute. It uses raw `aiohttp` internally. The entire plugin install step in the setup wizard crashes. Users who enter any plugin slugs during setup will see the installation fail at step 4.5 with no useful error.

**Fix:** Replace with a direct `aiohttp.ClientSession()` call to the Modrinth API, the same pattern used everywhere else in `mod_updater.py`.

---

## HIGH — wrong behaviour, data loss risk, security

### 3. `cogs/tasks.py` — `os.system()` inside async event loop
```python
playit_running = os.system("tmux has-session -t playit 2>/dev/null") == 0
os.system('tmux new-session -d -s playit "playit --secret ..."')
```
`os.system` is synchronous. It blocks the **entire bot** (all commands, all log streaming, all Discord responses) for the duration of the subprocess. Runs every 30 seconds.

**Fix:** Use `asyncio.create_subprocess_exec` or wrap in `asyncio.to_thread`.

---

### 4. `src/mc_link_manager.py` — race condition in `link_account`
```python
async def link_account(...):
    data = await self._read_data()   # lock acquired, then released
    # ... mutate data ...
    await self._write_data(data)     # lock acquired again separately
```
The lock is released between read and write. If two coroutines call `link_account` at the same time, the second read happens before the first write finishes. One write silently overwrites the other. This is in the security-critical module that prevents impersonation.

**Fix:** Hold one `async with self.lock:` block around the entire read-modify-write.

---

### 5. `src/join_guard.py` — `random` used for auth code
```python
code = str(random.randint(1000, 9999))
```
`random` is not cryptographically secure. Use `secrets.randbelow(9000) + 1000` instead.

---

### 6. `src/join_guard.py` — RCON injection via newline characters
```python
escaped_reason = reason.replace('"', '\\"')
cmd = f'kick {username} "{escaped_reason}"'
```
Only `"` is escaped. A username or code containing `\n` or `\r` could inject a second RCON command. Add stripping of control characters before building the command.

---

## MEDIUM — wrong results, silent bad state

### 7. `src/config.py` — blocking HTTP call at import time
```python
with urllib.request.urlopen("http://ip-api.com/json/", timeout=3) as response:
    self.TIMEZONE = ...
```
This runs synchronously when the module is first imported, before the async event loop starts. Delays bot startup by up to 3 seconds on every boot. Fails silently to `'UTC'` on any network issue.

---

### 8. `cogs/automation.py` — disk read on every single log line
```python
while not self.stop_scan.is_set():
    line = await asyncio.wait_for(self.log_queue.get(), timeout=1.0)
    user_config = config.load_user_config()  # JSON file read on every line
    triggers = user_config.get('triggers', {})
```
A busy server can emit hundreds of log lines per second. This reads and parses `user_config.json` from disk for each one.

**Fix:** Cache the config, refresh every 30 seconds or on an explicit reload command.

---

### 9. `cogs/admin.py` — hardcoded container name in `/logs`
```python
container_name = "mc-bot"
proc = await asyncio.create_subprocess_exec('docker', 'logs', '--tail', str(lines), container_name, ...)
```
Breaks on any deployment where the container was renamed. Also: the fallback reads `mc-server/logs/latest.log` but `log_dispatcher.py` already tails this same file — two different code paths for what the user sees as "the same logs".

---

### 10. `cogs/control_panel.py` — potential `IndexError` when cleaning old messages
```python
if "Control Panel" in str(old_msg.embeds[0].title if old_msg.embeds else ""):
```
If `old_msg.embeds` is a non-empty list but the first embed has no `.title` (returns `None`), `str(None)` evaluates to `"None"` and the check silently fails to match. If the embed list is empty the conditional short-circuits correctly, but this is fragile.

---

### 11. `cogs/tasks.py` — restart counter resets after giving up
```python
if self.restart_attempts >= 2:
    # ... notify owner ...
    self.restart_attempts = 0  # resets the counter
    return
```
After two failed restarts and owner notification, the counter resets to 0. The next crash restarts the whole cycle — two more attempts, another owner ping, reset again. The intention was to stop trying after 2 failures, but it retries indefinitely.

---

### 12. `src/server_tmux.py` — state saved before confirming server started
```python
res = await loop.run_in_executor(None, self._run_tmux_cmd, ["new-session", ...])
if res.returncode != 0:
    return False, msg

self._intentional_stop = False
self._start_time = time.time()
await self._save_state()  # saved as "running" even if Java crashes 2 seconds later
```
State is written as "intentionally running" the moment the tmux session opens, not when the Minecraft server is actually accepting connections. If Java fails to start (bad JAR, wrong Java version, OOM), the state file says the server is up and the crash checker won't trigger.

---

### 13. `src/log_dispatcher.py` — subscriber queues have no maxsize
```python
def subscribe(self) -> asyncio.Queue:
    q = asyncio.Queue()  # unlimited
    self._subscribers.append(q)
    return q
```
If a subscriber cog is slow (e.g., Discord rate-limited), its queue grows without bound. On a chatty server this can consume significant memory over time. The architecture diagram in the poročilo claims `maxsize=100` — the code disagrees.

---

## LOW — won't crash, but wrong or fragile

### 14. `cogs/console.py` — variable shadowing
```python
match = re.search(r'\[(.*?)] \[(.*?)/(.*?)\]: (.*)', line)
if match:
    ...
    elif "joined the game" in msg:
        match = re.match(r'^(\w+) joined the game', msg)  # shadows outer `match`
```
The outer `match` object is overwritten. Works by coincidence because the outer one isn't used again after this point, but a future change inside this block could silently read the wrong match groups.

---

### 15. Bare `except:` clauses throughout the codebase
Bare `except:` catches `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`, which can prevent clean shutdown. Found in:
- `cogs/players.py` — `except: return []`
- `cogs/control_panel.py` — `except: pass` (multiple)
- `src/mod_updater.py` — `except Exception: continue`

Should be `except (json.JSONDecodeError, OSError):` etc. with specific types.

---

### 16. `cogs/economy.py.disabled` listed in the command table
`/balance` appears in the docs and poročilo as a working command for all users. The file is disabled (`.disabled` extension) and the command is never registered. Users who try `/balance` get "Unknown command".

---

### 17. `requirements.txt` — no version pins
```
discord.py>=2.0.0
```
Any future `discord.py 3.x` with breaking API changes will be installed automatically on a fresh deploy. Pin to `>=2.3.0,<3.0.0` at minimum.

---

### 18. Two duplicate `ControlView` implementations
`src/views.py::ControlView` and `cogs/control_panel.py::ControlPanelView` both implement Start/Stop/Restart/Status buttons. `ControlView` is used by `/control` in `management.py`. Neither knows about the other. Two code paths to maintain for the same functionality.

---

### 19. `src/server_tmux.py` — potential `OSError` in `_save_state`
```python
await asyncio.to_thread(os.makedirs, os.path.dirname(self._state_file), exist_ok=True)
```
`self._state_file = os.path.join(config.SERVER_DIR, 'bot_state.json')`. If `SERVER_DIR` is a root-level path, `os.path.dirname` returns `''` (empty string). `os.makedirs('')` raises `FileNotFoundError`.

---

### 20. `src/backup_manager.py` — docs/code mismatch on upload provider
The code uses `transfer.sh` via raw HTTP POST. Every doc comment, the poročilo, and `docs/information.md` reference `pyonesend`. `pyonesend` is not in `requirements.txt`. Whichever one is intended, the other reference needs to be removed.