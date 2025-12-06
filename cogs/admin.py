import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from src.config import config
from src.utils import rcon_cmd, send_debug
from src.logger import logger

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="cmd", description="Execute RCON command")
    async def cmd(self, interaction: discord.Interaction, command: str):
        await interaction.response.defer(ephemeral=True)
        res = await rcon_cmd(command)
        # Discord has a 2000 char limit, truncate if needed
        if len(res) > 1900:
            res = res[:1900] + "..."
        await interaction.followup.send(f"```{res}```", ephemeral=True)

    @app_commands.command(name="sync", description="Sync commands")
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = discord.Object(id=config.GUILD_ID)
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            await interaction.followup.send(f"✅ Synced {len(synced)} commands.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)

    @app_commands.command(name="backup_now", description="Trigger immediate backup")
    async def backup_now(self, interaction: discord.Interaction, name: str = "manual"):
        await interaction.response.defer(ephemeral=True)
        from src.backup_manager import backup_manager
        
        await interaction.followup.send("⏳ Starting backup...", ephemeral=True)
        success, result = await backup_manager.create_backup(custom_name=name)
        
        if success:
            await interaction.followup.send(f"✅ Backup created: `{result}`", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Backup failed: {result}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
