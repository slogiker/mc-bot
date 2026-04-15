import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import json
import aiohttp
from collections import deque
from src.config import config
from src.utils import rcon_cmd, send_debug, has_role
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

    @app_commands.command(name="logs", description="Show last N log lines")
    @has_role("logs")
    async def logs(self, interaction: discord.Interaction, lines: int = 10):
        import aiofiles
        try:
            # Use docker logs to get the last N lines
            # This avoids issues with file locking or path resolution and matches console.py's approach
            container_name = os.getenv("CONTAINER_NAME", "mc-bot")
            # Check if running in container or if we can access docker
            
            proc = await asyncio.create_subprocess_exec(
                'docker', 'logs', '--tail', str(lines), container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                # Fallback to file reading if docker fails (e.g. not in docker group or name mismatch)
                # But for now, report error to help debug
                err_msg = stderr.decode().strip()
                if "No such container" in err_msg:
                     # Try fallback to 'mc-server' if that's the container name? 
                     # The bot tails 'mc-bot' in console.py, so we assume 'mc-bot'.
                     pass
                logger.warning(f"Docker logs failed: {err_msg}")
                
                # Fallback to file interaction
                path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
                if os.path.exists(path):
                    dq = deque(maxlen=lines)
                    async with aiofiles.open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        async for line in f:
                            dq.append(line.rstrip())
                    log_output = "\n".join(dq)
                else:
                    await interaction.response.send_message(f"❌ Docker logs failed and log file not found.", ephemeral=True)
                    return
            else:
                 log_output = stdout.decode('utf-8', errors='ignore').strip()

            # Clean up ANSI codes if necessary, or wrap in ansi block
            # For simplicity, we just send it.
            
            # Format as code block
            log_message = "```ansi\n" + log_output + "\n```"

            # Send to log channel as per original bot behavior
            log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            if log_channel:
                 await log_channel.send(f"📜 Last {lines} lines:\n{log_message}")
                 await interaction.response.send_message("✅ Logs sent to log channel.", ephemeral=True)
            else:
                 await interaction.response.send_message(f"Last {lines} lines:\n{log_message}", ephemeral=True)

        except Exception as e:
             logger.error(f"Failed to get logs: {e}")
             await interaction.response.send_message(f"❌ Failed to get logs: {e}", ephemeral=True)

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

    async def _modrinth_search(self, query: str, limit: int = 5) -> list[dict]:
        """Search Modrinth for mods/plugins. Returns list of hit dicts."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                params = {"query": query, "limit": limit}
                async with session.get("https://api.modrinth.com/v2/search", params=params) as resp:
                    if resp.status == 200:
                        return (await resp.json()).get("hits", [])
        except Exception:
            pass
        return []

    @app_commands.command(name="mod_search", description="Search Modrinth for mods or plugins by name")
    @app_commands.describe(query="Mod or plugin name (select a result to see details and get the slug)")
    async def mod_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=True)
        hits = await self._modrinth_search(query, limit=5)
        if not hits:
            await interaction.followup.send("No results found on Modrinth.", ephemeral=True)
            return

        lines = ["**Top Modrinth results** — copy a slug into the `/setup` plugins step:\n"]
        for hit in hits:
            name = hit.get("title", "?")
            slug = hit.get("slug", "?")
            summary = hit.get("description", "")[:80]
            project_type = hit.get("project_type", "")
            type_icon = "🔧" if project_type == "plugin" else "🧩" if project_type == "mod" else "📦"
            lines.append(f"{type_icon} **{name}** — slug: `{slug}`\n  *{summary}*")

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @mod_search.autocomplete("query")
    async def mod_search_autocomplete(self, interaction: discord.Interaction, current: str):
        if len(current) < 2:
            return []
        hits = await self._modrinth_search(current, limit=5)
        return [
            app_commands.Choice(
                name=f"{h.get('title', '?')} ({h.get('slug', '?')})"[:100],
                value=h.get("slug", "")
            )
            for h in hits
        ]


async def setup(bot):
    await bot.add_cog(Admin(bot))
