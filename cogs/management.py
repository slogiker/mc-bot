import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.utils import send_debug

class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def has_role(self, cmd_name):
        async def predicate(interaction):
            user_role_ids = [str(role.id) for role in interaction.user.roles]
            for role_id in user_role_ids:
                if cmd_name in config.ROLES.get(role_id, []):
                    return True
            await send_debug(self.bot, f"Check failed: {interaction.user.mention} lacks role for command '{cmd_name}'.")
            await interaction.response.send_message("❌ Prosim, dobi ustrezno vlogo.", ephemeral=True)
            return False
        return app_commands.check(predicate)

    def in_command_channel(self):
        async def predicate(interaction):
            if interaction.channel_id != config.COMMAND_CHANNEL_ID:
                await interaction.response.send_message(f"Use <#{config.COMMAND_CHANNEL_ID}>", ephemeral=True)
                return False
            return True
        return app_commands.check(predicate)

    @app_commands.command(name="control", description="Spawn the Control Panel")
    async def control(self, interaction: discord.Interaction):
        from src.views import ControlView
        embed = discord.Embed(title="🎛️ Minecraft Server Control", description="Manage the server using the buttons below.", color=0x5865F2)
        embed.add_field(name="Status", value="🟢 Online" if self.bot.server.is_running() else "🔴 Offline")
        await interaction.response.send_message(embed=embed, view=ControlView(self.bot))

    @app_commands.command(name="start", description="Start the server")
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
            # Log monitoring will handle the rest
        else:
            embed = discord.Embed(description="❌ Failed to start server.", color=0xED4245)
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="stop", description="Stop the server")
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

async def setup(bot):
    await bot.add_cog(Management(bot))
