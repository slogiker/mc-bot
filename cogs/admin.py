import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import json
from collections import deque
from src.config import config
from src.utils import rcon_cmd, send_debug, has_role
from src.logger import logger

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="cmd", description="Execute RCON command")
    @has_role("cmd")
    async def cmd(self, interaction: discord.Interaction, command: str):
        await interaction.response.defer(ephemeral=True)
        res = await rcon_cmd(command)
        if len(res) > 1900:
            res = res[:1900] + "..."
        await interaction.followup.send(f"```{res}```", ephemeral=True)

    @app_commands.command(name="sync", description="Sync commands")
    @has_role("sync")
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if not guild:
                 guild = discord.Object(id=config.GUILD_ID) if config.GUILD_ID else None
            
            if guild:
                self.bot.tree.copy_global_to(guild=guild)
                synced = await self.bot.tree.sync(guild=guild)
                await interaction.followup.send(f"✅ Synced {len(synced)} commands.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Could not determine guild.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)

    @app_commands.command(name="backup_now", description="Trigger immediate backup")
    @has_role("backup_now")
    async def backup_now(self, interaction: discord.Interaction, name: str = "manual"):
        await interaction.response.defer(ephemeral=True)
        from src.backup_manager import backup_manager
        
        await interaction.followup.send("⏳ Starting backup...", ephemeral=True)
        success, result = await backup_manager.create_backup(custom_name=name)
        
        if success:
            await interaction.followup.send(f"✅ Backup created: `{result}`", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Backup failed: {result}", ephemeral=True)

    @app_commands.command(name="reload_config", description="Reload config.json")
    @has_role("reload_config")
    async def reload_config(self, interaction: discord.Interaction):
        try:
            config.load()
            await interaction.response.send_message("🔄 Config reloaded.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to reload: {e}", ephemeral=True)

    @app_commands.command(name="logs", description="Show last N log lines")
    @has_role("logs")
    async def logs(self, interaction: discord.Interaction, lines: int = 10):
        # Default line count hardcoded or from config if accessible
        try:
            path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
            if not os.path.exists(path):
                await interaction.response.send_message("❌ Log file not found.", ephemeral=True)
                return

            dq = deque(maxlen=lines)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for L in f:
                    dq.append(L.rstrip())
            
            log_message = "```" + "\n".join(dq) + "```"
            # Send to log channel as per original bot behavior?
            # Original sent to log channel AND replied to user.
            log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            if log_channel:
                 await log_channel.send(f"📜 Last {lines} lines:\n{log_message}")
                 await interaction.response.send_message("✅ Logs sent to log channel.", ephemeral=True)
            else:
                 await interaction.response.send_message(f"Last {lines} lines:\n{log_message}", ephemeral=True)

        except Exception as e:
             await interaction.response.send_message(f"❌ Failed to get logs: {e}", ephemeral=True)

    @app_commands.command(name="whitelist_add", description="Add user to whitelist")
    @has_role("whitelist_add")
    async def whitelist_add(self, interaction: discord.Interaction, username: str):
        try:
            await interaction.response.defer(ephemeral=True)
            res = await rcon_cmd(f"whitelist add {username}")
            await rcon_cmd("whitelist reload")
            await interaction.followup.send(f"➕ {res}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
