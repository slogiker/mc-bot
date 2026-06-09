import discord
from discord import app_commands
from discord.ext import commands
import argparse
import asyncio
import sys
import os
import signal
import time
from src.config import config
from src.logger import logger
from src.server_tmux import TmuxServerManager
from src.log_dispatcher import log_dispatcher
from src.log_watcher import LogWatcher
from src.join_guard import JoinGuard
from src.utils import rcon_cmd

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Minecraft Discord Bot")
parser.add_argument("--simulate", action="store_true", help="Run in Simulation/Ghost Mode (No file/system changes)")
args = parser.parse_args()

# --- Configuration Setup ---
is_simulation = args.simulate
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
        
        # Initialize Security modules
        self.join_guard = JoinGuard(self)
        self.log_watcher = LogWatcher(self)
        self.presence_task = None
        
        # Attach event listener
        self.add_listener(self.on_minecraft_player_login, 'on_minecraft_player_login')

    async def update_presence_loop(self):
        """Background task to update bot presence based on server and RCON status."""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                is_running = self.server.is_running()
                
                # Start/Stop background log tasks based on server state
                if is_running:
                    if not log_dispatcher._running:
                        await log_dispatcher.start()
                        self.log_watcher.start()
                
                if is_running:
                    # Try RCON handshake
                    success, _ = await rcon_cmd("list")
                    
                    if success:
                        await self.change_presence(
                            activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Online"),
                            status=discord.Status.online
                        )
                    else:
                        # Check if it's been starting for a while
                        status_text = "Minecraft Server: Starting..."
                        if hasattr(self.server, 'get_start_time'):
                            start_time = self.server.get_start_time()
                            if start_time and (time.time() - start_time) > 180: # 3 minutes timeout
                                status_text = "Minecraft Server: ⚠️ RCON unavailable"
                        
                        await self.change_presence(
                            activity=discord.Activity(type=discord.ActivityType.playing, name=status_text),
                            status=discord.Status.idle
                        )
                else:
                    await self.change_presence(
                        activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Offline"),
                        status=discord.Status.dnd
                    )
            except Exception as e:
                logger.error(f"Error in presence update loop: {e}")
            
            # Fast sleep (10s) if starting, slow sleep (30s) if stable
            sleep_time = 10 if not self.server.is_running() or "Starting" in (getattr(self.user, 'activity', None).name if getattr(self.user, 'activity', None) else "") else 30
            await asyncio.sleep(sleep_time)

    # --- Event Handlers ---

    async def on_minecraft_player_login(self, username: str, uuid: str):
        """
        Dispatched custom event from LogWatcher when a user connects.

        Args:
            username (str): The Minecraft username of the player.
            uuid (str): The Minecraft UUID of the player.
        """
        await self.join_guard.handle_player_login(username, uuid)

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
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An unexpected error occurred. Technical details have been sent to the debug channel.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ An unexpected error occurred. Technical details have been sent to the debug channel.", ephemeral=True)

        # Send detailed report to debug channel
        try:
            debug_channel_id = config.DEBUG_CHANNEL_ID
            if debug_channel_id:
                channel = self.get_channel(int(debug_channel_id))
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
                
            cmd_name = interaction.command.name if interaction.command else "Unknown"
            logger.info(f"Command '/{cmd_name}' triggered by user {interaction.user.name} ({interaction.user.id}) in channel {interaction.channel_id}")
                
            cmd_channel_id = config.COMMAND_CHANNEL_ID
            if not cmd_channel_id:
                return True # If it's not setup yet, allow anywhere (or setup command wouldn't work)
                
            # Allow /setup to be run anywhere by admins to fix channels if broken
            if interaction.command and interaction.command.name == "setup":
                return True
                
            if interaction.channel_id != int(cmd_channel_id):
                error_msg = f"❌ Commands can only be used in <#{cmd_channel_id}>."
                await interaction.response.send_message(error_msg, ephemeral=True)
                return False
                
            return True
            
        self.tree.interaction_check = restrict_command_channel
            
        logger.info("=== Bot Startup: Loading Extensions ===")
        # Load cogs - wrap os.listdir for async
        loaded_count = 0
        try:
            filenames = await asyncio.to_thread(os.listdir, './cogs')
            for filename in filenames:
                if filename.endswith('.py') and not filename.startswith('_'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        logger.debug(f"Loaded cog: {filename}")
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f"Failed to load cog {filename}: {e}")
        except FileNotFoundError:
            logger.warning("No cogs directory found!")
        
        logger.info(f"=== {loaded_count} extensions loaded successfully ===")

    async def on_ready(self):
        """Called when bot is fully connected and ready."""
        logger.debug(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("=== Bot Connected to Discord ===")
        
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
            # Update memory config
            config.update_dynamic_config(updates)
            
            # Save to disk so we remember these IDs next time
            if updates:
                with config.update_bot_config() as data:
                    data.update(updates)
                logger.info(f"✅ Setup verified and IDs saved: {list(updates.keys())}")
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
        try:
            if self.server.is_running():
                await log_dispatcher.start()
                self.log_watcher.start()
        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")
        
        logger.info("=== Bot is now fully ready! ===")
        
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
        await bot.close()
    except Exception as e:
        logger.error(f"Error closing bot: {e}")
    
    logger.info("Shutdown complete")


async def main():
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

    logger.info("Starting bot client...")
    
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