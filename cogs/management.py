import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.utils import send_debug, has_role

class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def in_command_channel(self):
        async def predicate(interaction):
            if interaction.channel_id != config.COMMAND_CHANNEL_ID:
                await interaction.response.send_message(f"Use <#{config.COMMAND_CHANNEL_ID}>", ephemeral=True)
                return False
            return True
        return app_commands.check(predicate)

    @app_commands.command(name="control", description="Spawn the Control Panel")
    @has_role("control")
    async def control(self, interaction: discord.Interaction):
        from src.views import ControlView
        embed = discord.Embed(title="🎛️ Minecraft Server Control", description="Manage the server using the buttons below.", color=0x5865F2)
        embed.add_field(name="Status", value="🟢 Online" if self.bot.server.is_running() else "🔴 Offline")
        await interaction.response.send_message(embed=embed, view=ControlView(self.bot))

    @app_commands.command(name="start", description="Start the server")
    @app_commands.checks.cooldown(1, 30)  # 1 use per 30 seconds
    @has_role("start")
    async def start(self, interaction: discord.Interaction):
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
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(description="🛑 Stopping server...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        success, message = await self.bot.server.stop()
        if success:
            embed = discord.Embed(
                title="🛑 Server Stopped",
                description=message,
                color=0xED4245
            )
            # Update info channel
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
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
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(description="🔄 Restarting server...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        success, message = await self.bot.server.restart()
        if success:
            embed = discord.Embed(
                title="🚀 Server Restarted",
                description=message,
                color=0x57F287
            )
            # Update info channel
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
        else:
            embed = discord.Embed(
                title="❌ Failed to Restart Server",
                description=f"**Error:** {message}",
                color=0xED4245
            )
        
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="force_restart", description="Force restart server (simulated)")
    @has_role("force_restart")
    async def force_restart(self, interaction: discord.Interaction):
    @app_commands.command(name="bot_restart", description="Restart the bot")
    @has_role("bot_restart")
    async def api_bot_restart(self, interaction: discord.Interaction):
        import sys
        import os
        await interaction.response.send_message("🔄 Restarting bot...", ephemeral=True)
        os.execv(sys.executable, [sys.executable] + sys.argv)


async def setup(bot):
    await bot.add_cog(Management(bot))
