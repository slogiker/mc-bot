import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.utils import send_debug, has_role

class Management(commands.Cog):
    """
    Handles server lifecycle management and control commands.

    Includes starting, stopping, and restarting the Minecraft server,
    as well as managing the bot itself.
    """
    def __init__(self, bot):
        """Initializes the Management cog with the bot instance."""
        self.bot = bot

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
        import sys
        await interaction.response.send_message("Restarting bot...", ephemeral=True)
        # Use sys.exit instead of os.execv - Docker restart policy handles the actual restart
        # os.execv replaces PID 1 in Docker which can cause the container to exit uncleanly
        await self.bot.close()
        sys.exit(0)



async def setup(bot):
    await bot.add_cog(Management(bot))
