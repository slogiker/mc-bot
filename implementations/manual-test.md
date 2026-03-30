# mc-bot — Manual Test Report
**Date:** 2026-03-16  
**Tester:** slogiker  
**Environment:** CM4 (compute module 4), Docker, fresh clone via `setup.sh`

---

## Summary

| # | Severity | Area | Status |
|---|----------|------|--------|
| 1 | 🔴 High | `automation.py` cog | Broken — does not load |
| 2 | 🟠 Medium | `interaction_check` coroutine | RuntimeWarning on startup |
| 3 | 🔴 High | RCON | Refused for 60s, then timeout |
| 4 | 🔴 High | Playit — secret key extraction | Fails silently in install.sh |
| 5 | 🟠 Medium | Playit — no Docker service | `no such service: playit` |
| 6 | 🟡 Low | install.sh — misleading footer | Wrong instructions shown after setup |
| 7 | 🟠 Medium | ModUpdater — wrong context | Runs as "update" on fresh install |
| 8 | 🟡 Low | ModUpdater — unnecessary backup | Backup folder created even when mods folder is empty |
| 9 | 🔴 High | ModUpdater — `essential` fetch | `'ModUpdater' object has no attribute 'client'` |

---

## Bug Details

---

### BUG-01 — `automation.py` cog fails to load
**Severity:** 🔴 High  
**Log line:**
```
ERROR    Failed to load cog automation.py: Extension 'cogs.automation' raised an error:
         AttributeError: 'AutomationCog' object has no attribute 'motd_loop'
```
**Description:**  
`AutomationCog` references `self.motd_loop` but the attribute does not exist on the object at load time. This likely means `motd_loop` is defined as a `@tasks.loop` decorated method but is either missing, renamed, or not being attached to the cog instance correctly.

**Impact:** The entire `automation` cog is skipped. Any automation features (MOTD, scheduled tasks) are completely non-functional.

**Fix:**  
Check `cogs/automation.py` — ensure `motd_loop` is defined as a `@tasks.loop` method on `AutomationCog` and that it is started in `cog_load` or `__init__`. If the method was renamed or removed, update all references.

---

### BUG-02 — `interaction_check` coroutine never awaited
**Severity:** 🟠 Medium  
**Log lines:**
```
ERROR    [TERMINAL] RuntimeWarning: coroutine 'CommandTree.interaction_check' was never awaited
ERROR    [TERMINAL]   await self.setup_hook()
```
**Description:**  
A custom `CommandTree.interaction_check` is an `async` method but is being called without `await` somewhere inside `setup_hook`. Python creates the coroutine object but never executes it.

**Impact:** Interaction permission checks are silently skipped on every command invocation — a potential security/logic issue depending on what `interaction_check` enforces.

**Fix:**  
Find where `interaction_check` is called in `bot.py` or the custom `CommandTree` subclass. Change `self.tree.interaction_check(...)` to `await self.tree.interaction_check(...)`, or restructure so it is properly awaited in the async context.

---

### BUG-03 — RCON connection refused / 60s timeout
**Severity:** 🔴 High  
**Log lines:**
```
ERROR    RCON failed (list): The remote server refused the connection.
[... repeats every 2s for ~60s ...]
WARNING  Server started but RCON not available after 60s timeout
```
**Description:**  
The bot starts polling RCON immediately after launching the Minecraft process, but RCON is not available. Two possible root causes:

- `server.properties` does not have `rcon.enable=true` set (or the `/setup` command doesn't write it)
- The Minecraft server takes longer than 60s to fully start on this hardware (CM4), so RCON simply isn't ready in time

**Root cause:** `rcon.enable=true` is written to `server.properties` during setup by server initialization, but file isnt created at the time of trying reaching it. RCON is disabled by default in vanilla Minecraft, but it should be enabled by bot itself, if its not proceed with ths fix.

**Impact:** All RCON-dependent commands (`/tps`, `/list`, debug commands, etc.) fail permanently after startup.

**Fix:**  
Find the `server.properties` configuration step (likely in the `/setup` command handler or `ServerManager`) and restore the following lines being written:
```properties
enable-rcon=true
rcon.port=25575
rcon.password=<password from config>
```
Also consider logging a human-readable error ("RCON is disabled in server.properties") instead of spamming "connection refused" every 2 seconds.

---

### BUG-04 — Playit secret key extraction fails in `install.sh`
**Severity:** 🔴 High  
**Log line (install.sh output):**
```
[ERROR] Could not extract Playit secret key. You may need to configure the tunnel manually.
```
**And later in bot logs:**
```
WARNING  No Playit secret key found. Cannot fetch IP.
```
**Description:**  
After the user claims the Playit agent via the browser link, `install.sh` attempts to extract the secret key from the Playit agent's output or config file but fails. The key is never written to `data/playit_secret.key`, so the bot cannot fetch the tunnel address.

**Impact:** Playit tunnel is completely non-functional. The bot cannot report the server's public IP to players.

**Fix:**  
Review the key extraction logic in `install.sh`. The Playit CLI stores the secret key in a predictable config path after claiming — verify the path and parsing logic. Also add a fallback prompt asking the user to paste the key manually if auto-extraction fails.

---

### BUG-05 — No `playit` Docker service defined
**Severity:** 🟠 Medium  
**Commands run:**
```
docker compose logs -f playit
→ no such service: playit
```
**Description:**  
`docker-compose.yml` does not define a `playit` service. The Playit binary runs inside the `mc-bot` container rather than as a separate service. However, the install.sh completion message explicitly tells the user to run `docker compose logs -f playit`, which fails immediately.

**Impact:** Confusing for users — the command silently fails with no useful feedback.

**Fix:**  
Either:
- Remove the `playit` service reference from install.sh output (see BUG-06), or
- Add a proper `playit` service to `docker-compose.yml` if the architecture requires it

---

### BUG-06 — install.sh completion message is misleading / wrong
**Severity:** 🟡 Low  
**Shown after setup completes:**
```
Your bot should be online in Discord.
Run: /setup in Discord to initialize channels.

To view logs: docker compose logs -f mc-bot
To start tunnel: docker compose logs -f playit (if configured)
```
**Two problems:**
1. `docker compose logs -f playit` **views logs**, it does not **start** a tunnel. The label "To start tunnel:" is factually wrong.
2. `playit` is not a service (see BUG-05), so this command fails entirely.

**Fix:**  
Replace the footer with accurate instructions:
```
Your bot is now online in Discord.
Run /setup in Discord to finish server configuration.

To view bot logs:    docker compose logs -f mc-bot
To view Playit logs: docker exec mc-bot cat /app/logs/playit.log
```
Adjust paths to match actual Playit log output location.

---

### BUG-07 — ModUpdater runs on fresh install with "update" framing
**Severity:** 🟠 Medium  
**Log lines:**
```
INFO     ModUpdater: 🔍 Analyzing **5** local files...
INFO     ModUpdater: 📦 Moved old files to `old_mods_2026-03-16_09-17/`
INFO     ModUpdater: 📡 Downloading updates for Minecraft `1.21.11` (fabric)...
INFO     ModUpdater: ✨ Update complete! Successfully downloaded **6** new `.jar` files.
```
**Description:**  
On a completely fresh install with no mods present, ModUpdater still:
- Describes the operation as an "update" (not an "install")
- Says it analyzed "5 local files" when the `mc-server/` directory was empty
- Says it moved "old files" to a backup folder when there were no old files, but old folder was created (see BUG-08)
- Says it downloaded "updates" when these are first-time installs

The "5 local files" likely refers to default mods bundled inside the Docker image at `/app/mc-server/mods/` at build time — but from the user's perspective, no mods existed.

**Impact:** Confusing log output. It looks like mods existed before and were updated, when in reality this was a clean install.

**Fix:**  
Add a check before running the update flow:
- If no mods exist → log as **"Installing mods for the first time"**, skip backup step, skip "analyzing local files" step
- If mods exist → run the current update flow as normal

---

### BUG-08 — ModUpdater creates unnecessary backup folder on empty mods directory
**Severity:** 🟡 Low  
**Log line:**
```
INFO     ModUpdater: 📦 Moved old files to `old_mods_2026-03-16_09-17/`
```
**Description:**  
Even when the mods directory has no user-placed files (or only default bundled jars), ModUpdater creates a timestamped backup folder. This creates clutter and implies something was backed up when nothing meaningful existed.

**Impact:** Junk `old_mods_*` directories accumulate on every bot startup/update cycle.

**Fix:**  
Only create the backup folder if the mods directory actually contains files. Add a guard:
```python
if len(existing_mods) > 0:
    # create backup folder and move files
```

---

### BUG-09 — `essential` mod fetch fails: `'ModUpdater' object has no attribute 'client'`
**Severity:** 🔴 High  
**Log line:**
```
ERROR    Failed to fetch requested plugin/mod 'essential': 'ModUpdater' object has no attribute 'client'
```
**Description:**  
When attempting to download the `essential` mod, `ModUpdater` tries to use `self.client` (likely an `aiohttp.ClientSession`) but it has not been initialized. The session is either never created, created too late, or not assigned to `self.client` on the instance.

**Impact:** Any mod explicitly requested by name (via `/mod add essential` or similar) fails with an unhandled attribute error. Only the built-in update flow works because it likely uses a different code path.

**Fix:**  
Ensure `aiohttp.ClientSession` is created in `ModUpdater.__init__` or `cog_load`, and assigned to `self.client` before any download methods are called. Example:
```python
async def cog_load(self):
    self.client = aiohttp.ClientSession()
```
Also add cleanup in `cog_unload`:
```python
async def cog_unload(self):
    await self.client.close()
```

---

## Open Questions

- [ ] **BUG-07:** Confirm where the "5 local files" come from — are they bundled in the Docker image or copied from `data/`?
- [ ] **BUG-04:** What does Playit CLI store the secret key as after claiming — file path? Environment variable?

---

## What Was Working ✅

- Bot connects to Discord and logs in successfully
- Dynamic setup (roles, channels, category) runs correctly
- 16/17 cogs load successfully
- Slash commands sync (34 commands)
- ModUpdater correctly downloads and names mod JARs (despite wrong framing)
- EULA acceptance and `server.properties` base configuration work
- Docker build and container startup work cleanly
