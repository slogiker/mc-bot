# REVIEW_NOTES

## Section 2 — Repository Structure
Status: REWRITE
Issue: Lists `economy.py.disabled` at line 103 and `cogs/economy.py` at line 701 — actual file is `_economy.py` (underscore prefix, not `.disabled` suffix). Also `player_tracker.py` cog exists in the directory but is absent from the structure listing.

## Section 3.2 — Log Dispatcher (Subscribers list)
Status: REWRITE
Issue: Lists `economy.py` as an active subscriber — `_economy.py` is excluded from the auto-loader and not loaded, so it is not a subscriber at runtime.

## Section 4.5 — Config Attributes at Runtime (WORLD_FOLDER row)
Status: REWRITE
Issue: States `WORLD_FOLDER` is `hardcoded` and value is `"world"` — it is now a `@property` that reads `level-name` from `server.properties` with a `"world"` fallback; it is not hardcoded.

## Section 8 — Cog Reference: cogs/backup.py (Retention note)
Status: REWRITE
Issue: States "Auto backups in `backups/auto/` are deleted after `backup_keep_days` days. Custom backups in `backups/custom/` are never auto-deleted." — this is correct. However scheduled backups are correctly routed to `auto_dir`. The section does not note that the `/backup` command with no name also routes to `auto_dir` (not `custom_dir` as implied by Section 5's command table which says "else `backups/auto/`"), so the Section 5 table is accurate but the cog-reference prose should clarify scheduled backups always go to `auto_dir` and thus always have retention applied.

## Section 8 — Cog Reference: cogs/tasks.py
Status: REWRITE
Issue: Does not mention (a) crash_check guards against missing `server.jar` for fresh-install protection, (b) `start()` return value is now properly unpacked as `success, _ =` so crash retry counter works correctly, (c) Playit restart uses `bash -c` wrapper inside `tmux new-session`, (d) `online_players` is cleared on crash detection in addition to stop and startup.

## Section 8 — Cog Reference: cogs/economy.py
Status: REWRITE
Issue: Section header and body reference `cogs/economy.py` — the file has been renamed to `cogs/_economy.py` to exclude it from the dynamic cog auto-loader; the section should reflect the rename and clarify this is the mechanism that disables it.

## Section 9 — Source Module Reference: src/backup_manager.py
Status: REWRITE
Issue: Does not mention that `create_backup(custom_name=None)` routes unnamed calls to `auto_dir` (not `custom_dir`), which means scheduled (unnamed) backups now get retention cleanup applied — this is a behaviour change from previous versions.

## Section 10.4 — Open Issues #2 (WORLD_FOLDER hardcoded)
Status: REWRITE
Issue: Issue #2 lists `config.py` WORLD_FOLDER as hardcoded as "world" and open — this has been fixed; WORLD_FOLDER is now a `@property` reading `level-name` from `server.properties`.

## Section 15 — Deployment Notes: Healthcheck
Status: REWRITE
Issue: States "Docker restarts the container automatically after 3 failed `psutil` checks probing PID 1" — the healthcheck is actually `pgrep -f 'python bot.py'` defined in `docker-compose.yml`, not a psutil check, and it checks for the bot process, not PID 1.

## Section 2 — Repository Structure: Dockerfile entry
Status: REWRITE
Issue: Dockerfile description mentions "git" as an installed apt package — `git` is not present in the current Dockerfile apt install list, and `COPY data/` is not in the Dockerfile (data/ is mounted as a volume only); the description should not imply git is installed.

## Section 11 — Version History: signal handler change
Status: ADD
Issue: No version history entry documents the `bot.py` signal handler change from `signal.signal()` to `loop.add_signal_handler()` for async-safe SIGINT/SIGTERM handling.

## Section 11 — Version History: requirements.txt pinning and aio-mc-rcon PyPI
Status: ADD
Issue: No version entry documents that all deps are now pinned in `requirements.txt` and the git-source dep for `aio-mc-rcon` was replaced with the PyPI release `aio-mc-rcon==3.4.2`.
