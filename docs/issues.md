# Known Issues & Potential Failure Scenarios

> Written during code review after merging dev branch into main.
> Priority: P1 = breaks core functionality, P2 = bad UX / data loss risk, P3 = minor / cosmetic.

---

## P0 — Operational (Not Code Bugs)

### 0. Infinite server restart loop after pulling new code
**Symptom:** Logs show "Server started successfully" followed 29s later by "Server process not found — attempting restart" on a loop.  
**Cause:** Docker used a cached image layer that still contains the old buggy restart counter code (where `restart_attempts` reset to 0 instead of incrementing). The server is also likely crashing immediately because no `server.jar` exists yet (haven't run `/setup`).  
**Fix:** Force a clean rebuild — the cached layer won't be used:
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```
Then run `/setup` in Discord to install the Minecraft server.

---

## P1 — Will Break Under Certain Conditions

### 1. `join_guard.py` — Player kicked but DM never received
**File:** `src/join_guard.py:102–115`  
**Scenario:** Player joins with offline-mode protection active. Bot kicks them with "Check your Discord DMs". But if the player has DMs disabled from non-friends, `user.send()` throws `discord.Forbidden`. The exception is caught generically (`except Exception`) and logged, but the player is **already kicked** and will never receive the verification code. They have no way to proceed.  
**Result:** Player is permanently locked out unless manually whitelisted.  
**Fix needed:** Catch `discord.Forbidden` specifically and either (a) send the code in the commands channel mentioning the user, or (b) skip the kick and let them in with a warning to the server owner.

---

### 2. `setup_views.py` — No `on_timeout` handler
**File:** `src/setup_views.py:416`  
**Scenario:** User starts `/setup`, gets halfway through the wizard, then walks away for 10+ minutes. The `SetupView(timeout=600)` expires. Discord disables all buttons. The ephemeral message is now a dead UI with no explanation.  
**Result:** User has to run `/setup` again from the start with no indication of what happened.  
**Fix needed:** Add `async def on_timeout(self)` to edit the message with "Setup timed out — run /setup again."

---

### 3. `cogs/tasks.py` — Restart counter never resets on successful recovery
**File:** `cogs/tasks.py`  
**Scenario:** Server crashes → attempt 1 restarts successfully → `restart_attempts` is reset to 0. Server crashes again minutes later → attempt 1 again, fine. But if `restart_attempts` somehow reaches `> 2` (e.g. from a previous run stored in memory across a bot restart), `_intentional_stop` gets set silently without any notification.  
**Actual issue found:** After the notification is sent at `== 2`, `restart_attempts` is incremented to 3. On the next crash detection loop tick, `> 2` sets `_intentional_stop = True` silently and returns — but the server is still down. No further messages are sent. Owner was already notified at step 2, so this is acceptable, but `_intentional_stop = True` prevents the crash checker from ever trying again in that session without a manual `/start`.  
**Status:** Acceptable behavior, but should be documented to the server owner in the notification message.

---

### 4. `cogs/playit.py` — Playit API response format may not match
**File:** `cogs/playit.py:99`  
**Scenario:** `/ip` calls `https://api.playit.gg/account/tunnels`. The code checks `tunnel.get("tunnel_type") == "minecraft-java"`. If the Playit API returns a different field name or value (Playit has changed their API format before), this check always fails and falls through to the `alloc` address fallback, which also might not match.  
**Result:** `/ip` returns "No tunnels configured" even though the tunnel is running and working fine.  
**Fix needed:** Add logging of the raw API response at debug level so mismatches are diagnosable. Consider also checking `"game_version"` field or relaxing the tunnel type check.

---

## P2 — Bad UX or Data Risk

### 5. `setup_views.py` — Plugin download silent failures
**File:** `src/setup_views.py` (plugin download block)  
**Scenario:** User enters a plugin slug like `essentialsX` (wrong capitalization or typo). The Modrinth API returns 404. The exception is caught with `except Exception as e` and logged to file only. The setup wizard continues as if nothing happened.  
**Result:** User thinks plugins installed, but they didn't. Server starts without them.  
**Fix needed:** Collect failed slugs and display them in the final success embed ("⚠️ Failed to install: essentialsX").

---

### 6. `log_dispatcher.py` — Queue full silently drops log lines
**File:** `src/log_dispatcher.py:93–95`  
**Scenario:** Server generates a large burst of log output (e.g. during world generation, startup, or a crash). Queue is capped at 100 entries. If a subscriber (e.g. log streaming cog) can't keep up, `put_nowait()` raises `QueueFull` which is silently caught with `pass`.  
**Result:** Log lines are dropped and never shown in Discord's `#mc-console`. No indication this is happening.  
**Acceptable?** Mostly yes — dropping display logs is better than crashing. But worth knowing.

---

### 7. `src/config.py` — Timezone race condition on startup
**File:** `src/config.py`  
**Scenario:** The timezone is fetched in a background daemon thread. If a backup or scheduled task fires in the first ~3 seconds of startup before the HTTP request to ip-api.com completes, `self.TIMEZONE` will be `'UTC'` even if the user is in a different timezone.  
**Result:** First scheduled event/backup of the session may fire at UTC time, not local time. Corrects itself after the thread finishes.  
**Fix needed:** Low priority. Could log "Timezone resolved to X" when the thread completes.

---

### 8. `cogs/tasks.py` — Playit restart uses shell=True with unquoted variable
**File:** `cogs/tasks.py:138`  
**Code:** `asyncio.create_subprocess_shell('tmux new-session -d -s playit "playit --secret $(cat /app/data/playit_secret.key)"')`  
**Scenario:** This passes a shell string with a subshell `$(...)` to `create_subprocess_shell`. This is intentional and works, but if `playit_secret.key` contains whitespace or special characters (unlikely but possible if corrupted), the shell command will break silently.  
**Risk:** Low in practice since the key is a hex/base64 string, but worth noting.

---

### 9. `setup_views.py` — `_save_config_to_file` failure not surfaced
**File:** `src/setup_views.py` (inside `_start_installation`)  
**Scenario:** If `_save_config_to_file()` fails (e.g. disk full, permission error on `data/`), the exception propagates to the outer `except Exception as e` block which shows a red "Installation failed" embed. But the Minecraft server may have already been downloaded and started by that point.  
**Result:** Server is running but bot config is not saved. On next restart, bot has no channel/role IDs and can't function.  
**Fix needed:** Run `_save_config_to_file` first, before downloading the server jar.

---

## P3 — Minor / Cosmetic

### 10. `setup_views.py` — Confirmation step shows "latest" version literally
**File:** `src/setup_views.py:548–553`  
**Scenario:** User picks "latest" version. Confirmation summary shows `Version: latest (Latest available will be used)`. The actual resolved version is only fetched during download. The summary is therefore vague.  
**Note:** There's already a comment in the code acknowledging this (`# Note: We can't easily await here`). Could be fixed by resolving the version on the navigate-to-confirmation step.

---

### 11. `cogs/automation.py` — Trigger cache not invalidated on trigger changes
**File:** `cogs/automation.py`  
**Scenario:** The 30s trigger cache means that if a user adds a `/trigger_add` command, new triggers won't fire for up to 30 seconds after.  
**Result:** Slight delay before new triggers work. Not a bug, just expected behavior worth documenting to users.

---

### 12. `cogs/backup.py` — Backup download link expiry
**Scenario:** `/backup_download` returns a Discord attachment or file URL. Discord CDN URLs expire after a period. If a user saves the link and tries to use it later, it won't work.  
**Status:** Discord limitation, nothing we can do. Worth noting in the help text for `/backup_download`.

---

## P2 — Docker Build Performance

### 13. `Dockerfile` / `docker-compose.yml` — 400s+ build time, stale cache causes invisible code changes
**Files:** `Dockerfile`, `docker-compose.yml`  
**Scenario:** `docker compose up --build` takes 400+ seconds. The main culprit is the large `apt-get` layer (Java 21 + Playit install). Cache was intentionally disabled during testing because Docker sometimes served a cached layer that didn't reflect recent code changes — meaning bot.py/cogs edits weren't visible in the running container without a `--no-cache` build.  
**Root cause:** The `COPY bot.py / cogs/ / src/` steps are correctly placed after `pip install` to benefit from layer caching, but the `CACHEBUST` arg in docker-compose invalidates everything on every rebuild anyway. The Playit PPA install alone is slow and re-runs unnecessarily.  
**Goal:** Fast iterative rebuilds for code changes (should be <10s), full rebuild only when dependencies actually change.  
**Ideas to explore:**
- Split the Dockerfile into a stable base image (Java + Playit + pip deps) and a thin app layer (just COPY of .py files) — code changes only rebuild the app layer
- Use a pre-built base image pushed to a registry so the apt layer is never re-run locally
- Remove `CACHEBUST` from docker-compose (it defeats all caching) and instead rely on proper layer ordering
- For development: mount source files as a volume instead of COPYing them, so changes are instant without any rebuild

---

## Things to Test After Next Deployment

- [ ] Does `/setup` correctly restrict to `#mc-commands` channel only?
- [ ] Does the server crash checker correctly stop after 2 failed restarts and NOT loop indefinitely?
- [ ] Does Playit `/ip` return the correct address (check API field names against live response)?
- [ ] Do plugin slugs with typos show an error in Discord instead of silently failing?
- [ ] Does setup wizard timeout message show after 10 min of inactivity?
- [ ] Does the max players dropdown show "Currently: 5 Players" after navigating away and back?
