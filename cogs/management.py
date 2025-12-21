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
    @has_role("start")
    async def start(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.bot.server.is_running():
            embed = discord.Embed(description="✅ Server is already running.", color=0x57F287)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        success = await self.bot.server.start()
        if success:
            embed = discord.Embed(description="🚀 Server starting...", color=0x57F287)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(description="❌ Failed to start server.", color=0xED4245)
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="stop", description="Stop the server")
    @has_role("stop")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.bot.server.is_running():
            embed = discord.Embed(description="✅ Server is not running.", color=0x57F287)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(description="🛑 Stopping...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        success = await self.bot.server.stop()
        if success:
            embed = discord.Embed(description="🛑 Server stopped", color=0xED4245)
            await interaction.edit_original_response(embed=embed)
        else:
            embed = discord.Embed(description="❌ Failed to stop server.", color=0xED4245)
            await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="restart", description="Restart the server")
    @has_role("restart")
    async def restart(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(description="🔄 Restarting...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        success = await self.bot.server.restart()
        if success:
             embed = discord.Embed(description="🚀 Restarted.", color=0x57F287)
             await interaction.edit_original_response(embed=embed)
        else:
             embed = discord.Embed(description="❌ Failed to restart server.", color=0xED4245)
             await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="force_restart", description="Force restart server (simulated)")
    @has_role("force_restart")
    async def force_restart(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(description="🔄 Forcing Restart...", color=0xFEE75C)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # In current architecture, restart() handles stop/start sequence.
        # We can implement a more aggressive kill in ServerManager if needed.
        # For now, alias to restart.
        success = await self.bot.server.restart()
        if success:
             embed = discord.Embed(description="🚀 Forced restart done.", color=0x57F287)
             await interaction.edit_original_response(embed=embed)
        else:
             embed = discord.Embed(description="❌ Failed to force restart.", color=0xED4245)
             await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="bot_stop", description="Stop the bot")
    @has_role("bot_stop")
    async def api_bot_stop(self, interaction: discord.Interaction):
        import sys
        await interaction.response.send_message("🛑 Stopping bot...", ephemeral=True)
        sys.exit(0)

    @app_commands.command(name="bot_restart", description="Restart the bot")
    @has_role("bot_restart")
    async def api_bot_restart(self, interaction: discord.Interaction):
        import sys
        import os
        await interaction.response.send_message("🔄 Restarting bot...", ephemeral=True)
        os.execv(sys.executable, [sys.executable] + sys.argv)


async def setup(bot):
    await bot.add_cog(Management(bot))
