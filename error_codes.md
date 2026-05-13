# Error Codes

| Code    | Description                                                              | File:location                                                     |
|---------|--------------------------------------------------------------------------|-------------------------------------------------------------------|
| BOT_001 | Discord bot token missing or empty at startup                            | bot.py:main()                                                     |
| BOT_002 | Bot not in any guilds after connect — cannot perform setup               | bot.py:on_ready()                                                 |
| BOT_003 | Invalid or unparseable GUILD_ID in bot_config                            | bot.py:on_ready()                                                 |
| BOT_004 | Failed to sync slash commands to guild                                   | bot.py:on_ready()                                                 |
| BOT_005 | Dynamic setup (SetupHelper.ensure_setup) raised an exception             | bot.py:on_ready()                                                 |
| BOT_006 | Cog load failure — exception while loading a .py file from cogs/         | bot.py:setup_hook()                                               |
| BOT_007 | Unknown/unhandled AppCommandError dispatched to on_tree_error            | bot.py:on_tree_error()                                            |
| BOT_008 | Debug channel not found when trying to send error report                 | bot.py:on_tree_error()                                            |
| BOT_009 | /start command: server.start() returned failure                          | cogs/management.py:start()                                        |
| BOT_010 | /stop command: server.stop() returned failure                            | cogs/management.py:stop()                                         |
| BOT_011 | /restart command: server.restart() returned failure                      | cogs/management.py:restart()                                      |
| BOT_012 | /cmd: RCON_PASSWORD not set — RCON calls will fail                       | cogs/console.py:cmd()                                             |
| BOT_013 | /cmd: rcon_cmd() raised an exception                                     | cogs/console.py:cmd()                                             |
| BOT_014 | /logs: LOG_CHANNEL_ID not configured, falling back to ephemeral reply    | cogs/console.py:logs()                                            |
| BOT_015 | /sync: tree.sync() raised an HTTP exception                              | cogs/admin.py:sync()                                              |
| BOT_016 | /backup_now (admin): backup_manager.create_backup() raised exception     | cogs/admin.py:backup_now()                                        |
| BOT_017 | /whitelist_add: RCON error while adding user or reloading whitelist      | cogs/admin.py:whitelist_add()                                     |
| BOT_018 | Control panel message fetch failed (discord.NotFound) — resending        | cogs/control_panel.py:update_panel()                              |
| BOT_019 | Control panel channel not found (COMMAND_CHANNEL_ID missing/invalid)     | cogs/control_panel.py:update_panel()                              |
| BOT_020 | Control panel send failed (HTTPException or other)                       | cogs/control_panel.py:update_panel()                              |
| BOT_021 | Control panel button permission check uses config.ROLES which may be     | cogs/control_panel.py:_check_perm()                               |
|         | empty before resolve_role_permissions() runs                             |                                                                   |
| BOT_022 | /setup: Modrinth version fetch failed, using hardcoded fallback list     | src/setup_views.py:fetch_versions()                               |
| BOT_023 | /setup: mc_installer.download_server() failed during installation        | src/setup_views.py:_start_installation()                          |
| BOT_024 | /setup: EULA file accept failed (file I/O error)                         | src/setup_views.py:_start_installation()                          |
| BOT_025 | /setup: Plugin/mod download from Modrinth API failed for a slug          | src/setup_views.py:_start_installation()                          |
| BOT_026 | /setup: Server failed to start after installation                        | src/setup_views.py:_start_installation()                          |
| BOT_027 | /setup: RCON not available within 60s after server start                 | src/setup_views.py:_start_installation()                          |
| BOT_028 | /setup: bot_config.json save failed after Discord structure creation     | src/setup_views.py:_save_config_to_file()                         |
| BOT_029 | /setup: interaction timeout (10 min) — wizard abandoned mid-flow         | src/setup_views.py:SetupView.on_timeout()                         |
| BOT_030 | /settings RAM modal: invalid RAM format submitted (not digit+G/M)        | cogs/settings.py:RamModal.on_submit()                             |
| BOT_031 | /settings timezone modal: pytz not installed or invalid IANA name        | cogs/settings.py:TimezoneModal.on_submit()                        |
| BOT_032 | /settings schedule modal: invalid time string (missing colon)            | cogs/settings.py:ScheduleModal.on_submit()                        |
| BOT_033 | /help: ROLE_PERMISSIONS empty or not yet resolved — shows no commands    | cogs/help.py:help()                                               |
| BOT_034 | /stats: Mojang API timeout or 4xx for UUID lookup                        | cogs/stats.py:get_uuid_online()                                   |
| BOT_035 | /stats: NBT playerdata .dat file parse failure (nbtlib error)            | cogs/stats.py:get_stats_from_nbt()                                |
| BOT_036 | /stats: stats .json file parse failure (JSON decode error)               | cogs/stats.py:get_stats_from_nbt()                                |
| BOT_037 | /stats: no stats data found for player (new player or offline server)    | cogs/stats.py:stats()                                             |
| BOT_038 | /backup: backup_manager.create_backup() failed                           | cogs/backup.py:backup()                                           |
| BOT_039 | /backup_download: backup file not found in auto or custom dirs           | cogs/backup.py:backup_download()                                  |
| BOT_040 | /backup_download: discord.File send failed (file too large or HTTP err)  | cogs/backup.py:backup_download()                                  |
| BOT_041 | Scheduled backup loop: create_backup() failed                            | cogs/backup.py:backup_loop()                                      |
| BOT_042 | /mod_search: Modrinth search API timeout or error                        | cogs/mods.py:_modrinth_search()                                   |
| BOT_043 | /mod_search: version fetch or file download from Modrinth failed         | cogs/mods.py:ModrinthSearchView.handle_selection()                |
| BOT_044 | /mod_search: no compatible version found for slug+loader+MC version      | cogs/mods.py:ModrinthSearchView.handle_selection()                |
| BOT_045 | /update: server JAR download failed for target version                   | cogs/mods.py:update_everything()                                  |
| BOT_046 | /players_manage: RCON command returned "Unknown command" or "Error"      | cogs/players.py:PlayerManageSelect.callback()                     |
| BOT_047 | /players_manage: usercache.json / whitelist.json missing or malformed    | cogs/players.py:PlayersCog._read_json_safe()                      |
| BOT_048 | /info: psutil disk_usage failed (invalid path)                           | cogs/info.py:info()                                               |
| BOT_049 | /info: PlayitCog.tunnels empty — IP shows "Unknown"                      | cogs/info.py:info()                                               |
| BOT_050 | /event_create: event saved but LOG_CHANNEL_ID missing — reminder silent  | cogs/events.py:send_reminder()                                    |
| BOT_051 | event_loop: datetime.fromisoformat() fails on malformed event time       | cogs/events.py:event_loop()                                       |
| BOT_052 | trigger_add/remove: save_user_config failed — triggers not persisted     | cogs/automation.py:trigger_add() / trigger_remove()               |
| BOT_053 | Trigger scanner: RCON command for matched trigger raised exception        | cogs/automation.py:scan_logs_for_triggers()                       |
| BOT_054 | PlayerTracker: send_event_notification failed — DEBUG_CHANNEL_ID missing | cogs/player_tracker.py:send_event_notification()                  |
| BOT_055 | /setup: server.jar check uses SERVER_DIR which defaults to ./mc-server   | cogs/setup.py:setup()                                             |
|         | before bot_config is loaded — may misreport "already installed"          |                                                                   |
| MC_001  | Server jar not found at configured path — start() aborted                | src/server_tmux.py:start()                                        |
| MC_002  | Server directory does not exist — start() aborted                        | src/server_tmux.py:start()                                        |
| MC_003  | tmux new-session failed (non-zero exit) — server did not launch          | src/server_tmux.py:start()                                        |
| MC_004  | tmux not found in PATH — all tmux operations fail                        | src/server_tmux.py:_run_tmux_cmd()                                |
| MC_005  | tmux command timeout (>5s) — operation returns failure result            | src/server_tmux.py:_run_tmux_cmd()                                |
| MC_006  | stop() sends "stop" via tmux but server still running after 5s — force   | src/server_tmux.py:stop()                                         |
|         | kills session (world data may be partially written)                      |                                                                   |
| MC_007  | restart(): stop succeeded but start() failed — server left offline       | src/server_tmux.py:restart()                                      |
| MC_008  | State file (bot_state.json) load failure — defaults to intentional_stop  | src/server_tmux.py:_load_state()                                  |
| MC_009  | State file (bot_state.json) save failure — crash detection may misfire   | src/server_tmux.py:_save_state()                                  |
| MC_010  | Crash check loop aborted after 2 failed restart attempts                 | cogs/tasks.py:crash_check()                                       |
| MC_011  | Crash check: stale online_players not cleared on crash detection         | cogs/tasks.py:crash_check()                                       |
| MC_012  | server.jar absent at startup — crash check skips recovery silently       | cogs/tasks.py:crash_check()                                       |
| MC_013  | RCON password not set — rcon_cmd() will raise connection refused         | bot.py:main() (warning only)                                      |
| MC_014  | Log watcher: queue not subscribed before log_dispatcher starts —         | src/log_watcher.py:start()                                        |
|         | early log lines missed                                                   |                                                                   |
| MC_015  | LogDispatcher: latest.log does not exist — tail never starts             | src/log_dispatcher.py:_tail_logs()                                |
| MC_016  | LogDispatcher: tail -F subprocess exits unexpectedly — restarts in 2s    | src/log_dispatcher.py:_tail_logs()                                |
| MC_017  | LogDispatcher: subscriber queue full (maxsize=100) — lines silently      | src/log_dispatcher.py:_tail_logs()                                |
|         | dropped for that subscriber                                              |                                                                   |
| MC_018  | PlayerTracker: "joined the game" regex fails on non-ASCII username       | cogs/player_tracker.py:_consume()                                 |
| MC_019  | PlayerTracker log task never started if cog_load not awaited properly    | cogs/player_tracker.py:cog_load()                                 |
| MC_020  | AutomationCog log_queue not unsubscribed on cog_unload if never set      | cogs/automation.py:cog_unload()                                   |
| PT_001  | Playit secret key file missing and PLAYIT_SECRET_KEY env var not set     | cogs/playit.py:get_secret_key()                                   |
| PT_002  | Playit API returned 401 — secret key expired or invalid                  | cogs/playit.py:fetch_playit_address()                             |
| PT_003  | Playit API returned non-200 status — tunnel not claimed or API down      | cogs/playit.py:fetch_playit_address()                             |
| PT_004  | Playit API response contains no tunnels — none configured on account     | cogs/playit.py:fetch_playit_address()                             |
| PT_005  | Network error reaching api.playit.gg (aiohttp.ClientError)               | cogs/playit.py:fetch_playit_address()                             |
| PT_006  | Playit tunnel address parsed but has no display_address field            | cogs/playit.py:fetch_playit_address()                             |
| PT_007  | install.sh: playit claim generate returns empty — claim code not created | install/install.sh (Playit claim flow)                            |
| PT_008  | install.sh: playit claim exchange returns empty — secret key not obtained| install/install.sh (Playit claim flow)                            |
| PT_009  | install.sh: Playit agent tmux session fails to start after launch        | install/install.sh (Playit agent start)                           |
| PT_010  | install.sh: REST tunnel creation returns unexpected response             | install/install.sh (tunnel autocreate)                            |
| PT_011  | install.sh: agent_id not parseable from rundata API response             | install/install.sh (tunnel autocreate)                            |
| PT_012  | tasks.py: Playit tmux session absent — restart attempted up to 2 times   | cogs/tasks.py:crash_check() (Playit section)                      |
| PT_013  | tasks.py: Playit restart: new tmux session exits before verify sleep     | cogs/tasks.py:crash_check() (Playit section)                      |
| PT_014  | tasks.py: Playit crash loop aborted after 2 failed restart attempts      | cogs/tasks.py:crash_check() (Playit section)                      |
| CFG_001 | user_config.json not found — creates default (first run)                 | src/config.py:load()                                              |
| CFG_002 | user_config.json fails validation (invalid RAM, time format, etc.)       | src/config.py:load()                                              |
| CFG_003 | bot_config.json corrupt (JSON decode error) — recreated with defaults    | src/config.py:load()                                              |
| CFG_004 | Old config.json migration fails (missing keys or file I/O error)         | src/config.py:_migrate_old_config()                               |
| CFG_005 | Role name not found in guild during resolve_role_permissions              | src/config.py:resolve_role_permissions()                          |
| CFG_006 | Timezone auto-detect HTTP request to ip-api.com fails — defaults to UTC  | src/config.py:load() (fetch_tz thread)                            |
| CFG_007 | SetupHelper: guild.create_role() failed (missing bot permissions)        | src/setup_helper.py:ensure_setup()                                |
| CFG_008 | SetupHelper: guild.create_text_channel() failed (missing permissions)    | src/setup_helper.py:ensure_setup()                                |
| CFG_009 | SetupHelper: channel.edit() to move into category failed                 | src/setup_helper.py:ensure_setup()                                |
| CFG_010 | SetupHelper: guild.owner is None — owner role not auto-assigned          | src/setup_helper.py:_assign_owner_role()                          |
| CFG_011 | /settings: save_user_config fails — FileNotFoundError (data/ missing)    | cogs/settings.py (all Modal on_submit handlers)                   |
| CFG_012 | RCON_PASSWORD missing from .env — server commands silently fail          | bot.py:main() / src/utils.py                                      |
| CFG_013 | COMMAND_CHANNEL_ID None after setup — commands allowed anywhere          | bot.py:setup_hook:restrict_command_channel()                      |
| SYS_001 | Signal handler registration fails (NotImplementedError on Windows)       | bot.py:main()                                                     |
| SYS_002 | asyncio.to_thread fails (ThreadPoolExecutor exhausted under heavy load)  | src/server_tmux.py:start() / stop()                               |
| SYS_003 | java not found in PATH when starting server                              | src/server_tmux.py:start() (via tmux java_cmd)                    |
| SYS_004 | os.makedirs fails for data/ or backups/ directories (permission denied)  | src/config.py:_create_default_configs(), src/backup_manager.py    |
| SYS_005 | install.sh: Docker not installed and user declines auto-install          | install/install.sh:dependency check                               |
| SYS_006 | install.sh: docker compose / docker-compose not found                   | install/install.sh:step 4                                         |
| SYS_007 | install.sh: .env is a directory (Docker volume collision) — removed      | install/install.sh:env write                                       |
| SYS_008 | install.sh: openssl not available — RCON password generation fails       | install/install.sh:RCON_PASSWORD generation                       |
| SYS_009 | Log rotation: zipping rotated log file fails — original kept unzipped    | src/logger.py:rotator()                                           |
| SYS_010 | Log rotation: namer() receives unexpected filename format — fallback      | src/logger.py:namer()                                             |
| SYS_011 | LogDispatcher: asyncio.create_subprocess_exec("tail") not found (no tail)| src/log_dispatcher.py:_tail_logs()                                |
| DB_001  | bot_config.json save fails (disk full or permission denied)              | src/config.py:save_bot_config()                                   |
| DB_002  | user_config.json save fails (disk full or permission denied)             | src/config.py:save_user_config()                                  |
| DB_003  | bot_state.json (server state) save fails — intentional_stop not persisted| src/server_tmux.py:_save_state()                                  |
| DB_004  | bot_state.json load fails on startup — crash detection defaults safe     | src/server_tmux.py:_load_state()                                  |
| DB_005  | Backup zip write fails (world dir not found or disk full)                | src/backup_manager.py:_zip_world()                                |
| DB_006  | Auto backup cleanup: os.remove() fails for old backup file               | src/backup_manager.py:_cleanup_auto_backups()                     |
| DB_007  | bot_config.json FileLock contention causes blocking on slow filesystems  | src/config.py:load_bot_config() / save_bot_config()               |
| DB_008  | Playit secret key file write fails during install (data/ not created)    | install/install.sh / cogs/playit.py:get_secret_key()             |
| DB_009  | mc_links.json missing or corrupt — MCLinkManager fails to load links     | src/mc_link_manager.py (referenced by join_guard)                 |
| DB_010  | online_players list in bot_config grows unbounded if leave events missed | cogs/player_tracker.py:_consume() / cogs/tasks.py:crash_check()  |
