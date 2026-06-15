import discord
from discord import app_commands
from discord.ext import commands, tasks
from src.config import config
from src.utils import send_debug, has_role
import os
import time
from src.logger import logger

class Management(commands.Cog):
    """
    Handles server lifecycle management and control commands.

    Includes starting, stopping, and restarting the Minecraft server,
    as well as managing the bot itself.
    """
    def __init__(self, bot):
        """Initializes the Management cog with the bot instance."""
        self.bot = bot
        self.consecutive_restarts = 0
        self.auto_restart_loop.start()

    def cog_unload(self):
        self.auto_restart_loop.stop()

    @tasks.loop(seconds=60)
    async def auto_restart_loop(self):
        """Monitors the server and auto-restarts if it crashes."""
        try:
            if not self.bot.server.is_running() and not self.bot.server.is_intentionally_stopped():
                self.consecutive_restarts += 1
                logger.warning(f"⚠️ Server crash detected! Attempting auto-restart {self.consecutive_restarts}/3")
                
                if self.consecutive_restarts > 3:
                    logger.error("❌ Max auto-restart attempts reached. Server will remain offline.")
                    await self._notify_owner_of_failure()
                    return

                # Perform smart analysis for attempts 1 and 2
                crash_reason = await self._analyze_crash()
                logger.info(f"Crash Analysis: {crash_reason}")

                # Send debug alert
                debug_msg = f"⚠️ Server crashed! Auto-restart attempt {self.consecutive_restarts}/3\n**Analysis:** {crash_reason}"
                await send_debug(self.bot, debug_msg)

                # Attempt start
                success, msg = await self.bot.server.start()
                if success:
                    logger.info("✅ Auto-restart successful.")
                    # We don't reset consecutive_restarts here yet, wait for it to be stable
                    # or reset it if it stays up for X minutes. 
                    # For now, let's just wait.
                else:
                    logger.error(f"❌ Auto-restart failed: {msg}")

            elif self.bot.server.is_running():
                # Reset counter if server is running stably (e.g. for at least one loop cycle)
                if self.consecutive_restarts > 0:
                    self.consecutive_restarts = 0
                    logger.info("✅ Server is stable. Resetting crash counter.")
                    
        except Exception as e:
            logger.error(f"Error in auto-restart loop: {e}", exc_info=True)

    async def _analyze_crash(self) -> str:
        """Parses logs/latest.log to guess the crash reason."""
        log_path = os.path.join(config.SERVER_DIR, "logs", "latest.log")
        if not os.path.exists(log_path):
            return "No latest.log found."

        try:
            # Read last 50 lines
            with open(log_path, 'r') as f:
                lines = f.readlines()[-50:]
            
            log_text = "".join(lines).lower()
            
            if "java.lang.unsupportedclassversionerror" in log_text or "has been compiled by a more recent version" in log_text:
                return "❌ Java Version Mismatch (Server requires a newer Java version)."
            if "java.lang.outofmemoryerror" in log_text:
                return "❌ Out of Memory Error (Consider increasing RAM in settings)."
            if "failed to bind to port" in log_text:
                return "❌ Port already in use (Is another server running?)."
            if "exception stopping the server" in log_text:
                return "❌ Critical Exception during runtime."
            if "corrupt" in log_text:
                return "❌ Potential World/File Corruption detected."
            
            return "Unknown cause. Check logs/latest.log"
        except Exception as e:
            return f"Error reading logs: {e}"

    async def _notify_owner_of_failure(self):
        """Sends a high-priority alert pinging the owner in #debug."""
        debug_channel_id = config.DEBUG_CHANNEL_ID
        if not debug_channel_id:
            return

        channel = self.bot.get_channel(int(debug_channel_id))
        if not channel:
            try:
                channel = await self.bot.fetch_channel(int(debug_channel_id))
            except:
                return

        owner_ping = f"<@{config.OWNER_ID}>" if config.OWNER_ID else "@here"
        
        embed = discord.Embed(
            title="🛑 Server Persistent Crash",
            description="The Minecraft server has failed to start after 3 consecutive attempts and has been halted.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Last Analysis", value=await self._analyze_crash())
        embed.set_footer(text="Auto-restart loop suspended.")
        
        await channel.send(content=f"{owner_ping} 🚨 **URGENT: Server is stuck in a crash loop!**", embed=embed)

    # --- Server Control Commands ---

    @app_commands.command(name="control", description="Spawn the Control Panel")
    @has_role("control")
    async def control(self, interaction: discord.Interaction):
        """
        Sends an interactive control panel for the Minecraft server.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
        """
        from cogs.control_panel import ControlPanelView
        embed = discord.Embed(
            title="🎛️ Minecraft Server Control", 
            description="Manage the server using the buttons below.", 
            color=0x5865F2
        )
        embed.add_field(name="Status", value="🟢 Online" if self.bot.server.is_running() else "🔴 Offline")
        await interaction.response.send_message(embed=embed, view=ControlPanelView(self.bot))

    @app_commands.command(name="start", description="Start the server")
    @app_commands.checks.cooldown(1, 30)  # 1 use per 30 seconds
    @has_role("start")
    async def start(self, interaction: discord.Interaction):
        """
        Starts the Minecraft server.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=True)
        
        success, message = await self.bot.server.start()
        if success:
            embed = discord.Embed(
                title="🚀 Server Starting",
                description=message,
                color=0x57F287
            )
            # Update info channel
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
            
            # Update explicit presence
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name="Server Starting..."),
                status=discord.Status.idle
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Start Server",
                description=f"**Error:** {message}",
                color=0xED4245
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="stop", description="Stop the server")
    @app_commands.checks.cooldown(1, 30)  # 1 use per 30 seconds
    @has_role("stop")
    async def stop(self, interaction: discord.Interaction):
        """
        Stops the Minecraft server.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(description="🛑 Stopping server...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="Server Stopping..."),
            status=discord.Status.idle
        )
        
        success, message = await self.bot.server.stop()
        if success:
            embed = discord.Embed(
                title="🛑 Server Stopped",
                description=message,
                color=0xED4245
            )
            # Clear player list — stop doesn't fire individual "left the game" events
            try:
                with config.update_bot_config() as bot_cfg:
                    if bot_cfg.get('online_players'):
                        bot_cfg['online_players'] = []
            except Exception as e:
                from src.logger import logger
                logger.error(f"Failed to clear online players in stop: {e}")

            # Update info channel
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
            
            # Update explicit presence
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Offline"),
                status=discord.Status.dnd
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Stop Server",
                description=f"**Error:** {message}",
                color=0xED4245
            )
        
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="restart", description="Restart the server")
    @app_commands.checks.cooldown(1, 60)  # 1 use per 60 seconds
    @has_role("restart")
    async def restart(self, interaction: discord.Interaction):
        """
        Restarts the Minecraft server.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(description="🔄 Restarting server...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="Server Restarting..."),
            status=discord.Status.idle
        )
        
        # For a manual restart, we want to ensure it's not marked as intentional stop
        # so crash check doesn't ignore it if it takes too long to come up.
        if hasattr(self.bot.server, '_intentional_stop'):
            self.bot.server._intentional_stop = False

        success, message = await self.bot.server.restart()
        if success:
            embed = discord.Embed(
                title="🚀 Server Restarted",
                description=message,
                color=0x57F287
            )
            # Clear player list — restart doesn't fire individual "left the game" events immediately
            try:
                with config.update_bot_config() as bot_cfg:
                    if bot_cfg.get('online_players'):
                        bot_cfg['online_players'] = []
            except Exception as e:
                from src.logger import logger
                logger.error(f"Failed to clear online players in restart: {e}")

            # Update info channel
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
            
            # Update explicit presence (will be eventually overidden by the log monitor but good for instant feedback)
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name="Server Starting..."),
                status=discord.Status.idle
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Restart Server",
                description=f"**Error:** {message}",
                color=0xED4245
            )
        
        await interaction.edit_original_response(embed=embed)

    # --- Bot Management Commands ---

    @app_commands.command(name="kill", description="Emergency stop: Forcefully kill the server process")
    @has_role("stop")
    async def kill(self, interaction: discord.Interaction):
        """Forcefully kills the Minecraft server process."""
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(description="⚠️ Attempting emergency stop...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        success, message = await self.bot.server.emergency_stop()
        
        if success:
            embed = discord.Embed(
                title="💀 Server Force-Stopped",
                description="The server process was forcefully terminated.",
                color=0xED4245
            )
            # Clear player list
            try:
                with config.update_bot_config() as bot_cfg:
                    if bot_cfg.get('online_players'):
                        bot_cfg['online_players'] = []
            except Exception:
                pass
                
            # Update info channel
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
            
            # Update presence
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Offline"),
                status=discord.Status.dnd
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Force-Stop",
                description=f"**Error:** {message}",
                color=0xED4245
            )
            
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="bot_restart", description="Restart the bot")
    @has_role("bot_restart")
    async def api_bot_restart(self, interaction: discord.Interaction):
        """
        Restarts the Discord bot.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=False)
        msg = await interaction.followup.send("⏳ Restarting bot... Please wait.", wait=True)
        
        with config.update_bot_config() as data:
            data['restart_channel_id'] = msg.channel.id
            data['restart_message_id'] = msg.id

        # We don't call sys.exit() here because it raises SystemExit which the 
        # CommandTree logs as an error. bot.close() will cause bot.start() to 
        # return in main(), and the process will exit naturally.
        await self.bot.close()



async def setup(bot):
    await bot.add_cog(Management(bot))
