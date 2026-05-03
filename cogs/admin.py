import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.utils import rcon_cmd, has_role
from src.logger import logger

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    @app_commands.command(name="sync", description="Sync commands")
    @has_role("sync")
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild:
            self.bot.tree.copy_global_to(guild=interaction.guild)
            await self.bot.tree.sync(guild=interaction.guild)
        else:
            await self.bot.tree.sync()
        await interaction.followup.send("✅ Commands synced!", ephemeral=True)
    @app_commands.command(name="backup_now", description="Trigger immediate backup")
    @app_commands.checks.cooldown(1, 300)  # 1 use per 5 minutes
    @has_role("backup_now")
    async def backup_now(self, interaction: discord.Interaction, name: str = "manual"):
        try:
            await interaction.response.defer(ephemeral=True)
            from src.backup_manager import backup_manager
            
            await interaction.followup.send("⏳ Starting backup...", ephemeral=True)
            success, result, filepath = await backup_manager.create_backup(custom_name=name)
            
            if success:
                await interaction.followup.send(f"✅ Backup created: `{result}`", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Backup failed: {result}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in backup_now command: {e}", exc_info=True)
            try:
                await interaction.followup.send(f"❌ Backup command failed: {e}", ephemeral=True)
            except discord.HTTPException:
                pass

    @app_commands.command(name="whitelist_add", description="Add user to whitelist")
    @has_role("whitelist_add")
    async def whitelist_add(self, interaction: discord.Interaction, username: str):
        try:
            await interaction.response.defer(ephemeral=True)
            try:
                res = await rcon_cmd(f"whitelist add {username}")
                await rcon_cmd("whitelist reload")
                await interaction.followup.send(f"➕ {res}", ephemeral=True)
            except Exception as rcon_error:
                logger.error(f"RCON error in whitelist_add: {rcon_error}")
                await interaction.followup.send(f"❌ Failed to add to whitelist: {rcon_error}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in whitelist_add command: {e}", exc_info=True)
            try:
                await interaction.followup.send(f"❌ Command failed: {e}", ephemeral=True)
            except discord.HTTPException:
                pass

async def setup(bot):
    await bot.add_cog(Admin(bot))
