Minecraft Server Control Discord Bot
A powerful and modular Discord bot designed to manage a Minecraft server directly from Discord. This bot allows authorized users to start, stop, restart, and monitor the server, manage backups, view player stats, and execute RCON commands, all through a secure, role-based permission system.
Originally created by slogiker and refactored for clarity and maintainability.
Key Features
 * Full Server Control: Start, stop, and restart the server with simple slash commands.
 * Real-time Status: Get detailed server status, including online players, CPU/RAM usage, and uptime.
 * Role-Based Permissions: Finely-tuned access control. Assign specific commands (e.g., /start, /stop) to different Discord roles in the config.json.
 * Automated Tasks:
   * Crash Detection: Automatically restarts the server if it crashes.
   * Scheduled Backups: Performs daily backups at a configurable time.
   * Scheduled Restarts: Restarts the server nightly (only if no players are online).
 * Backup Management: Trigger backups manually at any time and manage a clean, rotating backup history.
 * Log Management: Automatically cleans up old log files to save space.
 * RCON Console: Execute any command directly on the Minecraft server console via a /cmd command in Discord.
Setup and Installation
Follow these steps to get your bot up and running.
Prerequisites
 * Python 3.8 or newer.
 * A dedicated Discord Bot account with an authentication token.
 * A Minecraft Java Edition server.
 * screen installed on the server host (for running the server process in the background).
1. Download the Code
Download the minecraft_bot.zip file and extract it to a folder on your server.
2. Install Dependencies
Navigate to the project directory in your terminal and install the required Python packages using the requirements.txt file:
pip install -r requirements.txt

3. Configure the Bot
You need to edit two configuration files: .env and config.json.
.env File
This file stores your secret credentials.
# .env
# Fill in your bot token and RCON password here
BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN"
RCON_PASSWORD="YOUR_RCON_PASSWORD"

config.json File
This file controls the bot's behavior and links it to your server and Discord channels.
 * "rcon_host" & "rcon_port": The IP and port for your server's RCON. 127.0.0.1 is correct if the bot runs on the same machine as the server.
 * "command_channel_id": The Discord channel ID where users will type commands.
 * "debug_channel_id": The channel ID where the bot will post startup, restart, and error messages.
 * "owner_role_id": The Discord role ID for the main administrator.
 * "guild_id": Your Discord server (Guild) ID.
 * "server_directory": The absolute path to your Minecraft server's main folder.
 * "server_jar": The exact filename of your server's .jar file (e.g., fabric-server-launch.jar).
 * "backup_time" & "restart_time": The times for scheduled backups and restarts in "HH:MM" format (24-hour clock).
 * "roles": This is where you set up permissions. Add Discord Role IDs and list the commands that role is allowed to use.
4. Run the Bot
Once configured, you can start the bot from your terminal:
python main.py

For continuous operation, it's recommended to run the bot within a screen session or as a systemd service.
Available Commands
All commands are slash commands (e.g., /start).
Server Management
 * /start - Starts the Minecraft server.
 * /stop - Stops the Minecraft server safely.
 * /restart - Restarts the Minecraft server safely.
Server Information
 * /status - Displays a detailed embed with the server's current status, player list, and resource usage.
 * /players - Shows a quick list of online players.
 * /version - Displays the Minecraft server version.
 * /stats [username] - View player statistics.
Administrative Commands
 * /backup_now - Triggers an immediate backup with a custom-backup filename.
 * /cmd [command] - Executes a command directly on the server console via RCON.
 * /sync - Manually syncs the bot's slash commands with Discord. Useful if commands aren't showing up.
This README.md file has been generated to provide clear and comprehensive documentation for your project.