# 📜 Command Cheatsheet

## 🤖 Discord Bot Commands

### Control

- `/start` - Start the Minecraft server.
- `/stop` - Stop the server (graceful shutdown).
- `/restart` - Restart the server.
- `/kill` - Force kill the server process (emergency only).
- `/cmd <command>` - Execute a console command (e.g., `/cmd op Player`).

### Information

- `/status` - Show if server is Online/Offline and player count.
- `/ip` - Show the public Playit.gg connection address.
- `/info` - Show host system stats (CPU, RAM, Disk).
- `/stats [player]` - Show playtime, death count, and join dates.

### Management

- `/backup` - Create a manual backup immediately.
- `/backup_list` - List all backups.
- `/backup_download <filename>` - Get a download link for a backup.
- `/logs [lines]` - Retrieve the last N lines of the server log file.
- `/whitelist_add <player>` - Add a player to the whitelist.

### Economy

- `/balance [user]` - Check coin balance.
- `/pay <user> <amount>` - Transfer coins to another user.
- `/economy_set <user> <amount>` - (Admin) Set a user's balance.

---

## 💻 Terminal / Docker Commands

Run these in your `mc-bot` directory (where `docker-compose.yml` is).

### Basics

| Action               | Command                                                    |
| :------------------- | :--------------------------------------------------------- |
| **Start Everything** | `docker compose up -d`                                     |
| **Stop Everything**  | `docker compose down`                                      |
| **Restart Bot**      | `docker compose restart mc-bot`                            |
| **Restart Tunnel**   | `docker compose restart playit`                            |
| **Update Bot**       | `git pull && docker compose build && docker compose up -d` |

### Logs & Debugging

| Action               | Command                            |
| :------------------- | :--------------------------------- |
| **View Bot Logs**    | `docker compose logs -f mc-bot`    |
| **View Tunnel Logs** | `docker compose logs -f playit`    |
| **Enter Container**  | `docker exec -it mc-bot /bin/bash` |
| **Check CPU/RAM**    | `docker stats`                     |

### Troubleshooting

- **Bot not starting?** Check logs: `docker compose logs mc-bot`
- **Tunnel not working?** Check logs: `docker compose logs playit`
- **Permission errors?** Ensure you are running as a user with Docker permissions.
