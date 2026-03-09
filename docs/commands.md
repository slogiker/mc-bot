# 📜 Command Cheatsheet

## 🤖 Discord Bot Commands

### Control

- `/start` - Start the Minecraft server.
- `/stop` - Stop the server (graceful shutdown).
- `/restart` - Restart the server.
- `/control` - Open an interactive control panel with Start/Stop/Restart/Status buttons.
- `/cmd <command>` - Execute a raw console command (e.g., `/cmd op Player`). Owner only.
- `/bot_restart` - Hot-restart the bot process without restarting the container.

### Information

- `/status` - Show if server is Online/Offline and player count.
- `/ip` - Show the public Playit.gg connection address.
- `/players` - List currently online players.
- `/version` - Show the Minecraft server version.
- `/seed` - Show the world seed.
- `/mods` - List installed mods/plugins.
- `/info` - Full server embed: IP, version, CPU, RAM, Disk, players, spawn.
- `/stats [player]` - Show playtime, death count, and join dates.
- `/set_spawn <x> <y> <z>` - Save custom spawn coordinates. Admin only.

### Management

- `/setup` - Run the interactive server setup wizard (version, platform, settings).
- `/sync` - Re-sync slash commands to the guild.
- `/backup [name]` - Create a backup (named = custom, unnamed = auto).
- `/backup_now [name]` - Trigger an immediate backup. 5 min cooldown.
- `/backup_list` - List the most recent auto + custom backups.
- `/backup_download <filename>` - Get a shareable download link for a backup.
- `/logs [lines]` - Retrieve the last N lines of the server log.
- `/whitelist_add <player>` - Add a player to the whitelist.

### Events

- `/event_create <name> <time> [description] [mentions]` - Schedule an event with automatic reminders.
- `/event_list` - Show all upcoming events.
- `/event_delete <index>` - Delete an event by its list index.

### Automation

- `/motd <text>` - Set the server MOTD via RCON (requires Essentials plugin).
- `/trigger_add <phrase> <command>` - Add a keyword→RCON command trigger.
- `/trigger_list` - Show all configured triggers.
- `/trigger_remove <phrase>` - Remove a trigger.

### Economy _(currently disabled)_

- `/balance [user]` - Check coin balance.
- `/pay <user> <amount>` - Transfer coins to another user.
- `/economy_set <user> <amount>` - (Admin) Set a user's balance.

### Misc

- `/help` - Dynamic help embed filtered by the caller's permissions.

---

## 💻 Terminal / Docker Commands

Run these in your `mc-bot` directory (where `docker-compose.yml` is).

### Basics

| Action               | Command                                                    |
| :------------------- | :--------------------------------------------------------- |
| **Start Everything** | `docker compose up -d`                                     |
| **Stop Everything**  | `docker compose down`                                      |
| **Restart Bot**      | `docker compose restart mc-bot`                            |
| **Update Bot**       | `python install/update.py`                                 |

### Logs & Debugging

| Action                       | Command                                         |
| :--------------------------- | :---------------------------------------------- |
| **View Bot Logs**            | `docker compose logs -f mc-bot`                 |
| **Enter Container**          | `docker exec -it mc-bot /bin/bash`              |
| **Attach MC Console**        | `docker exec -it mc-bot tmux attach -t minecraft` |
| **Attach Playit Session**    | `docker exec -it mc-bot tmux attach -t playit`  |
| **Check CPU/RAM**            | `docker stats`                                  |

### Troubleshooting

- **Bot not starting?** Check logs: `docker compose logs mc-bot`
- **Tunnel not working?** Enter the container and check the playit tmux session: `docker exec -it mc-bot tmux attach -t playit`
- **Permission errors?** Ensure you are running as a user in the `docker` group.
- **Setup wizard stuck?** Try `/sync` first, then run `/setup` again.
