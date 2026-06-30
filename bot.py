import discord
from discord import app_commands
from discord.ext import commands
import argparse
import asyncio
import sys
import os
import signal
import time
import logging
from src.config import config
from src.logger import logger
from src.server_tmux import TmuxServerManager
from src.log_dispatcher import log_dispatcher
from src.log_watcher import LogWatcher
from src.join_guard import JoinGuard
from src.utils import rcon_cmd, send_debug

# --- Discord Logging Handler ---
class DiscordDebugHandler(logging.Handler):
    """
    Custom logging handler that dispatches ERROR and CRITICAL logs 
    to the Discord debug channel asynchronously.
    """
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.setLevel(logging.ERROR)
        self._is_sending = False

    def emit(self, record):
        # Prevent recursion if sending fails
        if self._is_sending:
            return
            
        # We must use the bot's event loop to send the message
        try:
            if not self.bot.loop.is_closed():
                self.bot.loop.create_task(self._send_to_discord(record))
        except:
            pass

    async def _send_to_discord(self, record):
        self._is_sending = True
        try:
            msg = self.format(record)
            # Truncate if too long for Discord
            if len(msg) > 1900:
                msg = msg[:1900] + "..."
            
            # Use the existing send_debug utility
            await send_debug(self.bot, msg)
        except:
            pass # Silently fail to avoid loops
        finally:
            self._is_sending = False

# --- Argument Parsing ---
def parse_args():
    parser = argparse.ArgumentParser(description="Minecraft Discord Bot")
    parser.add_argument("--simulate", action="store_true", help="Run in Simulation/Ghost Mode (No file/system changes)")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    remove_world_parser = subparsers.add_parser("remove-world", help="Remove the Minecraft world folder")
    remove_world_parser.add_argument("--simulate", action="store_true", help="Run in Simulation/Ghost Mode (No file/system changes)")
    
    if __name__ == "__main__":
        return parser.parse_args()
    else:
        return parser.parse_known_args([])[0]

args = parse_args()

# --- Configuration Setup ---
is_simulation = getattr(args, "simulate", False)
config.set_simulation_mode(is_simulation)

# --- Bot Setup ---
class MinecraftBot(commands.Bot):
    """
    The main Discord bot class for managing the Minecraft server.

    Attributes:
        server (TmuxServerManager | MockServerManager): The server manager instance.
        synced (bool): Flag to prevent duplicate command syncs.
        join_guard (JoinGuard): Module for managing player logins and verification.
        log_watcher (LogWatcher): Module for monitoring server logs.
    """
    def __init__(self):
        """Initializes the MinecraftBot with necessary intents and managers."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='/', intents=intents)
        
        # Initialize Server Manager
        if is_simulation:
            from src.server_mock import MockServerManager
            logger.info("👻 GHOST MODE: Using MockServerManager")
            self.server = MockServerManager()
        else:
            self.server = TmuxServerManager()
        
        self.synced = False  # Prevent duplicate syncs
        self._sync_lock = asyncio.Lock()  # Prevent race conditions
        self.start_time = time.time()  # Track bot uptime
        self._startup_complete = False  # Track if initial setup is done
        self._disconnect_time = None  # Track when the bot disconnected from Discord
        
        # Initialize Security modules
        self.session = None  # Created in on_ready or similar
        self.join_guard = JoinGuard(self)
        self.log_watcher = LogWatcher(self)
        self.presence_task = None
        
        # Add Discord logging handler
        self._discord_handler = DiscordDebugHandler(self)
        if logger.handlers:
            self._discord_handler.setFormatter(logger.handlers[0].formatter)
        logger.addHandler(self._discord_handler)
        
        # Attach event listeners
        self.add_listener(self.on_minecraft_player_login,  'on_minecraft_player_login')
        self.add_listener(self.on_minecraft_player_quit,   'on_minecraft_player_quit')
        self.add_listener(self.on_minecraft_collision,     'on_minecraft_collision')
        self.add_listener(self.on_minecraft_started,       'on_minecraft_started')
        self.add_listener(self.on_minecraft_stopping,      'on_minecraft_stopping')

    async def update_presence(self):
        """Updates the bot's presence status immediately based on current server state."""
        try:
            from src.utils import rcon_cmd
            if self.server.is_running():
                # Try RCON handshake
                success, _ = await rcon_cmd("list")
                
                if success:
                    await self.change_presence(
                        activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Online"),
                        status=discord.Status.online
                    )
                else:
                    status_text = "Minecraft Server: Starting..."
                    start_time = getattr(self.server, 'get_start_time', lambda: None)()
                    if start_time and (time.time() - start_time) > 120:
                        status_text = "Minecraft Server: ⚠️ RCON unavailable"
                    
                    await self.change_presence(
                        activity=discord.Activity(type=discord.ActivityType.playing, name=status_text),
                        status=discord.Status.idle
                    )
            else:
                status_type = discord.Status.dnd
                if self.server.is_intentionally_stopped():
                    status_text = "Minecraft Server: Offline"
                else:
                    status_text = "Minecraft Server: ⚠️ Crashed"
                    
                await self.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.playing, name=status_text),
                    status=status_type
                )
        except Exception as e:
            logger.error(f"Error in update_presence: {e}")

    async def update_presence_loop(self):
        """Background task to update bot presence based on server and RCON status."""
        await self.wait_until_ready()
        while not self.is_closed():
            await self.update_presence()
            await asyncio.sleep(30)

    # --- Event Handlers ---

    async def on_minecraft_player_login(self, username: str, uuid: str):
        """
        Dispatched custom event from LogWatcher when a user connects.

        Args:
            username (str): The Minecraft username of the player.
            uuid (str): The Minecraft UUID of the player.
        """
        await self.join_guard.handle_player_login(username, uuid)

    async def on_minecraft_player_quit(self, username: str):
        """Dispatched custom event from LogWatcher when a player leaves."""
        self.join_guard.handle_player_quit(username)

    async def on_minecraft_collision(self, username: str):
        """Dispatched custom event from LogWatcher when a collision is detected."""
        await self.join_guard.handle_collision(username)

    async def on_minecraft_started(self):
        """Dispatched custom event from LogWatcher when 'Done' is detected."""
        logger.debug("Instant Presence Update: Server is Online")
        await self.update_presence()

    async def on_minecraft_stopping(self):
        """Dispatched custom event from LogWatcher when 'Stopping server' is detected."""
        logger.info("Detected graceful server shutdown. Marking as intentional stop to prevent spurious crash alerts.")
        self.server._intentional_stop = True
        await self.server._save_state()
        
        logger.debug("Instant Presence Update: Server is Stopping")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Stopping..."),
            status=discord.Status.dnd
        )

    async def start_background_tasks(self):
        """Starts background log monitoring tasks if not already running."""
        try:
            await log_dispatcher.start()
            self.log_watcher.start()
            logger.debug("Background log monitoring tasks ensured.")
        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """
        Global error handler for app commands.

        Args:
            interaction (discord.Interaction): The interaction that triggered the error.
            error (app_commands.AppCommandError): The error that occurred.
        """
        # Ignore cooldowns or permission errors for the debug channel, just show ephemeral to user
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ Command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
            return
        elif isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You cannot use this command here.", ephemeral=True)
            return

        # Handle unknown errors
        logger.error(f"Global Command error: {error}", exc_info=True)
        
        # Notify user ephemerally
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ An unexpected error occurred. Technical details have been sent to the debug channel.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ An unexpected error occurred. Technical details have been sent to the debug channel.", ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            pass
        except Exception as e:
            logger.error(f"Failed to notify user of error: {e}")

        # Send detailed report to debug channel
        try:
            debug_channel_id = config.DEBUG_CHANNEL_ID
            if debug_channel_id:
                channel = self.get_channel(int(debug_channel_id))
                if not channel:
                    try:
                        channel = await self.fetch_channel(int(debug_channel_id))
                    except:
                        channel = None

                if channel:
                    import traceback
                    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
                    
                    # Create embed
                    embed = discord.Embed(
                        title="🚨 Command Error", 
                        color=discord.Color.red(), 
                        timestamp=interaction.created_at
                    )
                    embed.add_field(name="User", value=f"{interaction.user} ({interaction.user.id})", inline=True)
                    embed.add_field(name="Command", value=f"/{interaction.command.name if interaction.command else 'Unknown'}", inline=True)
                    embed.add_field(name="Error Type", value=type(error).__name__, inline=False)
                    embed.add_field(name="Message", value=str(error), inline=False)
                    
                    # Owner ping logic
                    owner_ping = ""
                    if config.OWNER_ID:
                        owner_ping = f"<@{config.OWNER_ID}>"
                    
                    # Send with traceback in code block
                    msg = f"{owner_ping} A critical error occurred!"
                    
                    # Handle long tracebacks
                    if len(tb) > 1000:
                        tb = tb[-1000:] # Get last 1000 chars
                    
                    await channel.send(content=msg, embed=embed)
                    await channel.send(f"**Traceback:**\n```py\n{tb}\n```")
        except Exception as e:
            logger.error(f"Failed to send error report to debug channel: {e}")

    # --- Setup & Connection Hooks ---

    async def setup_hook(self):
        """Called during bot startup - load extensions but DON'T sync yet."""
        self.tree.on_error = self.on_tree_error
        
        # Initialize shared session
        import aiohttp
        self.session = aiohttp.ClientSession()
        logger.debug("Initialized shared aiohttp ClientSession")
        
        # Global command channel check
        async def restrict_command_channel(interaction: discord.Interaction) -> bool:
            """
            Check if the interaction is allowed in the current channel.

            Args:
                interaction (discord.Interaction): The interaction to check.

            Returns:
                bool: True if allowed, False otherwise.
            """
            # We only restrict actual slash commands
            if interaction.type != discord.InteractionType.application_command:
                return True
                
            cmd_channel_id = config.COMMAND_CHANNEL_ID
            if not cmd_channel_id:
                return True # If it's not setup yet, allow anywhere
                
            # Allow /setup to be run anywhere by admins to fix channels if broken
            if interaction.command and interaction.command.name == "setup":
                return True
                
            if interaction.channel_id != int(cmd_channel_id):
                # Self-healing check: Is the configured channel actually valid?
                configured_channel = interaction.client.get_channel(int(cmd_channel_id))
                
                if not configured_channel:
                    # The channel is gone or inaccessible!
                    if interaction.user.guild_permissions.administrator:
                        # Allow admins to use commands anywhere if the bot is "lost"
                        return True
                    else:
                        await interaction.response.send_message(
                            "❌ The configured command channel is missing or inaccessible. "
                            "Please ask a server administrator to run `/setup` to fix this.", 
                            ephemeral=True
                        )
                        return False
                
                error_msg = f"❌ Commands can only be used in {configured_channel.mention}."
                await interaction.response.send_message(error_msg, ephemeral=True)
                return False
                
            return True
            
        self.tree.interaction_check = restrict_command_channel
            
        logger.debug("=== Bot Startup: Loading Extensions ===")
        # Load cogs - wrap os.listdir for async
        loaded_count = 0
        try:
            filenames = await asyncio.to_thread(os.listdir, './cogs')
            for filename in filenames:
                if filename.endswith('.py') and not filename.startswith('_'):
                    if filename == 'playit.py' and not config.ENABLE_PLAYIT:
                        logger.info("Playit is disabled in configuration, skipping playit cog.")
                        continue
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        logger.debug(f"Loaded cog: {filename}")
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f"Failed to load cog {filename}: {e}")
        except FileNotFoundError:
            logger.warning("No cogs directory found!")
        
        logger.debug(f"=== {loaded_count} extensions loaded successfully ===")

    async def on_ready(self):
        """Called when bot is fully connected and ready."""
        logger.debug(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.debug("=== Bot Connected to Discord ===")
        
        if is_simulation:
            logger.info("👻 GHOST MODE ACTIVE: No files will be modified. Server is mocked.")

        # Only sync once (with lock to prevent race conditions)
        async with self._sync_lock:
            if self.synced:
                logger.info("Commands already synced, skipping...")
                return
        
            # Determine which Guild to use
            guild = None
            if config.GUILD_ID:
                try:
                    guild = self.get_guild(int(config.GUILD_ID))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid GUILD_ID: {config.GUILD_ID}")
        
        if not guild and self.guilds:
            guild = self.guilds[0]
            logger.info(f"No GUILD_ID configured, using first guild: {guild.name}")
             
        if not guild:
            logger.error("Bot is not in any guilds! Cannot perform setup.")
            logger.error("Please invite the bot to your Discord server.")
            return

        logger.info(f"Using Guild: {guild.name} ({guild.id})")

        # Run Dynamic Setup
        logger.debug("Running dynamic setup...")
        from src.setup_helper import SetupHelper
        setup_helper = SetupHelper(self)
        try:
            updates = await setup_helper.ensure_setup(guild)
            # Persist these to disk so they stay valid across restarts
            config.update_dynamic_config(updates, save=not is_simulation)
            logger.debug(f"Dynamic Config Updated & Persisted: {updates}")
        except Exception as e:
            logger.error(f"Dynamic Setup Failed: {e}", exc_info=True)
            
        # VERY IMPORTANT: Resolve roles so the @has_role decorators check IDs correctly
        logger.debug("Resolving role permissions...")
        config.resolve_role_permissions(guild)
        
        # Sync commands to this guild
        logger.debug("Syncing slash commands to guild...")
        try:
            self.tree.copy_global_to(guild=guild)
            synced_commands = await self.tree.sync(guild=guild)
            logger.info(f"✅ Synced {len(synced_commands)} commands to {guild.name}")
            self.synced = True
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}", exc_info=True)
            return

        # Start presence updater task
        if self.presence_task is None:
            self.presence_task = asyncio.create_task(self.update_presence_loop())

        # Ensure background tasks are running if the server is online
        if self.server.is_running():
            await self.start_background_tasks()
        
        # Mark startup as complete
        if not self._startup_complete:
            self._startup_complete = True

        # Check for pending bot restart message
        try:
            bot_cfg = config.load_bot_config()
            restart_channel_id = bot_cfg.get('restart_channel_id')
            restart_message_id = bot_cfg.get('restart_message_id')
            if restart_channel_id and restart_message_id:
                channel = self.get_channel(int(restart_channel_id))
                if channel:
                    msg = await channel.fetch_message(int(restart_message_id))
                    await msg.edit(content="✅ Bot restarted successfully!")
                
                with config.update_bot_config() as data:
                    data.pop('restart_channel_id', None)
                    data.pop('restart_message_id', None)
        except Exception as e:
            logger.error(f"Failed to update restart message: {e}")

        # Check for update/restart pending notification
        try:
            bot_cfg = config.load_bot_config()
            pending_type = bot_cfg.get('update_restart_pending')
            if pending_type:
                # Set intentional_stop to False and start the server in the background
                self.server._intentional_stop = False
                await self.server._save_state()
                asyncio.create_task(self.server.start())
                
                debug_channel_id = config.DEBUG_CHANNEL_ID
                if debug_channel_id:
                    channel = self.get_channel(int(debug_channel_id))
                    if channel:
                        if pending_type == 'update':
                            msg = "🔄 **Bot updated and restarted successfully!** (Pulled latest changes from repository). Starting Minecraft server..."
                        else:
                            msg = "🔄 **Bot restarted successfully!** Starting Minecraft server..."
                        await channel.send(msg)
                
                with config.update_bot_config() as data:
                    data.pop('update_restart_pending', None)
        except Exception as e:
            logger.error(f"Failed to send pending restart notification: {e}")

        # Check for Host Reboot / Power Loss on startup
        try:
            import psutil
            host_uptime = time.time() - psutil.boot_time()
            if host_uptime < 300: # Host booted less than 5 minutes ago
                intentional_stop = True
                if hasattr(self, 'server') and self.server:
                    intentional_stop = self.server.is_intentionally_stopped()
                
                if not intentional_stop:
                    debug_channel_id = config.DEBUG_CHANNEL_ID
                    if debug_channel_id:
                        channel = self.get_channel(int(debug_channel_id))
                        if channel:
                            await channel.send("🔌 **Host Reboot / Power Loss Detected!** The server host recently restarted (uptime: {:.0f}s) while the Minecraft server was online. Auto-recovering...")
        except Exception as e:
            logger.error(f"Failed to check host uptime: {e}")

        # Check if we were disconnected before
        if hasattr(self, '_disconnect_time') and self._disconnect_time:
            await self._report_reconnection()

        logger.debug("=== Bot is now fully ready! ===")

    async def on_disconnect(self):
        self._disconnect_time = time.time()
        logger.warning("Bot disconnected from Discord.")

    async def on_resumed(self):
        logger.info("Bot session resumed.")
        await self._report_reconnection()

    async def _report_reconnection(self):
        try:
            if hasattr(self, '_disconnect_time') and self._disconnect_time:
                duration = time.time() - self._disconnect_time
                self._disconnect_time = None # Reset
                if duration > 30: # Only report if disconnected for more than 30 seconds
                    debug_channel_id = config.DEBUG_CHANNEL_ID
                    if debug_channel_id:
                        channel = self.get_channel(int(debug_channel_id))
                        if channel:
                            await channel.send(f"🌐 **Internet Outage / Network Disruption Recovered!** The bot was disconnected from Discord for {duration:.0f} seconds before successfully reconnecting.")
        except Exception as e:
            logger.error(f"Failed to report reconnection: {e}")

# --- Lifecycle Management ---

async def shutdown_handler(bot):
    """
    Graceful shutdown - stop server and close bot cleanly.

    Args:
        bot (MinecraftBot): The bot instance to shut down.
    """
    logger.info("Shutdown initiated...")
    
    try:
        # Stop Minecraft server if running
        if bot.server and bot.server.is_running():
            logger.info("Stopping Minecraft server...")
            await bot.server.stop()
            logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Error stopping server during shutdown: {e}")
    
    try:
        # Close bot connection
        logger.info("Closing bot connection...")
        if bot.session:
            await bot.session.close()
            logger.info("Shared aiohttp session closed")
        
        from src.rcon_manager import rcon_manager
        await rcon_manager.close()
            
        await bot.close()
    except Exception as e:
        logger.error(f"Error closing bot: {e}")
    
    logger.info("Shutdown complete")


async def send_discord_debug_message(message: str):
    token = config.TOKEN
    channel_id = config.DEBUG_CHANNEL_ID
    if not token or not channel_id:
        print("[WARNING] Discord token or debug channel ID is not configured. Skipping debug channel ping.")
        return
    
    import aiohttp
    from datetime import datetime
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "content": f"[DEBUG] {message}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in (200, 201):
                    logger.error(f"Failed to send discord message: {resp.status} - {await resp.text()}")
                else:
                    print("Debug ping sent to Discord.")
    except Exception as e:
        logger.error(f"Failed to send discord message via HTTP: {e}")

async def handle_remove_world():
    world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
    
    # 1. Ping in Discord debug channel
    msg = "Subcommand remove-world initiated. Stopping Minecraft server and removing the world folder."
    if is_simulation:
        msg += " (SIMULATION MODE)"
    await send_discord_debug_message(msg)

    if not os.path.exists(world_path):
        print(f"World folder does not exist: {world_path}")
        print("You can now create a new world with /setup in Discord.")
        return

    # Check if server is running and stop it peacefully
    from src.server_tmux import TmuxServerManager
    from src.server_mock import MockServerManager
    server = MockServerManager() if is_simulation else TmuxServerManager()
    
    if server.is_running():
        print("Minecraft server is running. Stopping peacefully...")
        success, stop_msg = await server.stop()
        if success:
            print("Minecraft server stopped successfully.")
        else:
            print(f"Failed to stop Minecraft server: {stop_msg}")
            try:
                proceed = input("Do you want to proceed with world removal anyway? (y/n): ").strip().lower()
                if proceed not in ('y', 'yes'):
                    print("Operation cancelled.")
                    return
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return

    # Prompt user for backup
    try:
        response = input("Would you like to backup the world before deleting it? (y/n): ").strip().lower()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return

    if response in ('y', 'yes'):
        backup_dir = os.path.join("backups", "removed_worlds")
        if not is_simulation:
            os.makedirs(backup_dir, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f"world_backup_{timestamp}.zip")
        
        print(f"Creating backup at {backup_file}...")
        if not is_simulation:
            import zipfile
            try:
                with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(world_path):
                        for file in files:
                            if file == 'session.lock':
                                continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, world_path)
                            zf.write(file_path, arcname)
                print(f"Backup created successfully at: {backup_file}")
            except Exception as e:
                print(f"Failed to create backup: {e}")
                try:
                    proceed = input("Backup failed. Do you want to proceed with removing the world anyway? (y/n): ").strip().lower()
                    if proceed not in ('y', 'yes'):
                        print("Operation cancelled.")
                        return
                except KeyboardInterrupt:
                    print("\nOperation cancelled.")
                    return
        else:
            print(f"[SIMULATION] Would write zip to {backup_file}")

    elif response in ('n', 'no'):
        pass
    else:
        print("Invalid input. Operation cancelled.")
        return

    # Delete the world
    print(f"Removing world folder: {world_path}...")
    if not is_simulation:
        import shutil
        try:
            shutil.rmtree(world_path)
            print("World folder removed successfully.")
        except Exception as e:
            print(f"Failed to remove world folder: {e}")
            return
    else:
        print(f"[SIMULATION] Would delete world folder: {world_path}")

    print("You can now create a new world with /setup in Discord.")

    # Peacefully stop docker container
    if os.path.exists('/.dockerenv'):
        main_pid = 1
        if os.getpid() != main_pid:
            try:
                print("Peacefully stopping the main docker container process...")
                import signal
                os.kill(main_pid, signal.SIGTERM)
            except Exception as e:
                print(f"Failed to stop docker container: {e}")

async def main():
    if args.command == "remove-world":
        await handle_remove_world()
        return

    bot = MinecraftBot()
    token = config.TOKEN
    
    if is_simulation and ("DISCORD_TOKEN" in os.environ or "BOT_TOKEN" in os.environ):
         # In simulation, prefer the env var passed by simulate.py
         token = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")
    
    if not token:
        if is_simulation:
             logger.error("Simulation Error: DISCORD_TOKEN not provided (simulate.py should handle this)")
        else:
             logger.error("No token found! Check .env file for DISCORD_TOKEN")
        return

    if not config.RCON_PASSWORD:
        logger.warning("RCON_PASSWORD not set — server commands (start/stop/etc) will fail until it is configured in .env")

    # --- Startup Banner ---
    C_GREEN = "\033[38;5;118m" # Grass Green
    C_BROWN = "\033[38;5;130m" # Dirt Brown
    C_GRAY = "\033[38;5;245m"  # Stone Gray
    C_WHITE = "\033[97m"       # Bright White
    C_RESET = "\033[0m"
    C_BOLD = "\033[1m"
    
    print(f"""
{C_GREEN}      __  __  ____        ____   ___ _____ 
{C_GREEN}     |  \\/  |/ ___|      | __ ) / _ \\_   _|
{C_BROWN}     | |\\/| | |   _____  |  _ \\| | | || |  
{C_BROWN}     | |  | | |__|_____| | |_) | |_| || |  
{C_GRAY}     |_|  |_|\\____|      |____/ \\___/ |_|  {C_RESET}
    
{C_WHITE}{C_BOLD}     Minecraft Discord Bot{C_RESET}
{C_GRAY}     Crafting connections...{C_RESET}
    """)
    # ----------------------

    logger.debug("Starting bot client...")
    
    loop = asyncio.get_running_loop()

    def _schedule_shutdown():
        asyncio.create_task(shutdown_handler(bot))

    try:
        # add_signal_handler is async-safe — callbacks are scheduled on the event loop
        loop.add_signal_handler(signal.SIGINT, _schedule_shutdown)
        if hasattr(signal, 'SIGTERM'):
            loop.add_signal_handler(signal.SIGTERM, _schedule_shutdown)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler — use call_soon_threadsafe fallback
        signal.signal(signal.SIGINT, lambda s, f: loop.call_soon_threadsafe(_schedule_shutdown))
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, lambda s, f: loop.call_soon_threadsafe(_schedule_shutdown))
    except (ValueError, OSError):
        logger.warning("Could not register signal handlers")
    
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        # Print readable crash message to terminal
        import traceback
        print("\n" + "=" * 60)
        print("  MC-BOT CRASHED - Debug Information")
        print("=" * 60)
        print(f"  Error: {type(e).__name__}: {e}")
        print("-" * 60)
        traceback.print_exc()
        print("=" * 60)
    finally:
        pass  # Nothing to clean up at this level