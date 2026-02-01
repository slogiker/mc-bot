import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import aiofiles
from src.config import config
from src.utils import rcon_cmd, get_uuid, display_key, map_key, has_role, parse_server_version

from src.server_info_manager import ServerInfoManager

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.info_manager = ServerInfoManager(bot)

    @app_commands.command(name="status", description="Show Minecraft server status")
    @has_role("status")
    async def status(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(title="Minecraft Server Status")
            if self.bot.server.is_running():
                embed.color = 0x57F287 # Green
                try:
                    players_response = await rcon_cmd("list")
                    embed.add_field(name="Status", value="🟢 **Online**", inline=False)
                    embed.add_field(name="Players", value=f"```{players_response}```", inline=False)
                except Exception as e:
                    from src.logger import logger
                    logger.error(f"Failed to get player list in status command: {e}")
                    embed.add_field(name="Status", value="🟢 **Online**", inline=False)
                    embed.add_field(name="Players", value="```Unable to fetch player list```", inline=False)
            else:
                embed.color = 0xED4245 # Red
                embed.add_field(name="Status", value="🔴 **Offline**", inline=False)
            
            from datetime import datetime
            embed.set_footer(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            from src.logger import logger
            logger.error(f"Error in status command: {e}", exc_info=True)
            try:
                await interaction.response.send_message("❌ Failed to get server status.", ephemeral=True)
            except:
                pass

    @app_commands.command(name="players", description="List online players")
    @has_role("players")
    async def players(self, interaction: discord.Interaction):
        try:
            if not self.bot.server.is_running():
                embed = discord.Embed(description="🔴 Server is offline.", color=0xED4245)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            try:
                res = await rcon_cmd("list")
                embed = discord.Embed(title="Online Players", description=f"```{res}```", color=0x5865F2)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                from src.logger import logger
                logger.error(f"Failed to get player list: {e}")
                embed = discord.Embed(description="❌ Failed to get player list.", color=0xED4245)
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            from src.logger import logger
            logger.error(f"Error in players command: {e}", exc_info=True)
            try:
                await interaction.response.send_message("❌ Failed to get players.", ephemeral=True)
            except:
                pass

    @app_commands.command(name="version", description="Show server version")
    @has_role("version")
    async def version(self, interaction: discord.Interaction):
        try:
            ver = await parse_server_version()
            # Try to fetch real version via RCON or log parsing if possible, or use configured
            await interaction.response.send_message(f"🛠️ Server version: {ver}", ephemeral=True)
        except Exception as e:
            from src.logger import logger
            logger.error(f"Error in version command: {e}", exc_info=True)
            try:
                await interaction.response.send_message("❌ Failed to get server version.", ephemeral=True)
            except:
                pass

    @app_commands.command(name="seed", description="Displays the server seed")
    @has_role("seed")
    async def seed(self, interaction: discord.Interaction):
        try:
             # Try RCON first
             if self.bot.server.is_running():
                try:
                    seed_val = await rcon_cmd("seed")
                    await interaction.response.send_message(f"🌱 {seed_val}", ephemeral=True)
                    return
                except:
                    pass
             
             # Fallback to reading server.properties or level.dat logic in manager
             # For now just say server needs to be online or check logs
             await interaction.response.send_message("❌ Server must be online to check seed (or use /info).", ephemeral=True)

        except Exception as e:
             await interaction.response.send_message(f"❌ Failed to get seed: {e}", ephemeral=True)

    @app_commands.command(name="mods", description="Lists installed mods")
    @has_role("mods")
    async def mods(self, interaction: discord.Interaction):
        try:
            mods_dir = os.path.join(config.SERVER_DIR, 'mods')
            exists = await asyncio.to_thread(os.path.exists, mods_dir)
            if not exists:
                await interaction.response.send_message("❌ Mods folder not found.", ephemeral=True)
                return
            try:
                mods_list = [f for f in await asyncio.to_thread(os.listdir, mods_dir) if f.endswith('.jar')]
                if not mods_list:
                    await interaction.response.send_message("🧩 No mods installed.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"🧩 Installed mods:\n- " + "\n- ".join(mods_list), ephemeral=True)
            except OSError as e:
                from src.logger import logger
                logger.error(f"Failed to list mods directory: {e}")
                await interaction.response.send_message("❌ Failed to read mods directory.", ephemeral=True)
        except Exception as e:
            from src.logger import logger
            logger.error(f"Error in mods command: {e}", exc_info=True)
            try:
                await interaction.response.send_message("❌ Failed to get mods list.", ephemeral=True)
            except:
                pass

    @app_commands.command(name="info", description="Displays server information (updated)")
    @has_role("server_info")
    async def info(self, interaction: discord.Interaction):
        """Displays detailed server information"""
        await interaction.response.defer(ephemeral=True)
        try:
            # Trigger update of the info channel as well
            await self.info_manager.update_info(interaction.guild)
            
            # Show ephemeral info
            from src.logger import logger
            ver = await parse_server_version()
            
            # Get IP
            ip = "slogikerserver.ddns.net"
            
            # Get spawn
            spawn = self.info_manager._get_spawn() or "Not set"
            
            embed = discord.Embed(title="🌍 Server Information", color=0x5865F2)
            embed.add_field(name="IP Address", value=f"`{ip}`", inline=False)
            embed.add_field(name="Version", value=f"`{ver}`", inline=True)
            
            if self.bot.server.is_running():
                embed.add_field(name="Status", value="🟢 Online", inline=True)
                try:
                    players = await rcon_cmd("list")
                    embed.add_field(name="Players", value=f"```{players}```", inline=False)
                except:
                     embed.add_field(name="Players", value="Unknown", inline=False)
            else:
                embed.add_field(name="Status", value="🔴 Offline", inline=True)
            
            embed.add_field(name="Spawn", value=f"`{spawn}`", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            from src.logger import logger
            logger.error(f"Error in info command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Failed to get info: {e}", ephemeral=True)

    @app_commands.command(name="set_spawn", description="Set spawn coordinates for server info")
    @app_commands.describe(x="X coordinate", y="Y coordinate", z="Z coordinate")
    @has_role("MC Admin") # Only admins should do this (using heuristic role check or permission)
    async def set_spawn(self, interaction: discord.Interaction, x: int, y: int, z: int):
        if not interaction.user.guild_permissions.administrator:
             await interaction.response.send_message("❌ Only administrators can set spawn.", ephemeral=True)
             return
             
        await interaction.response.defer(ephemeral=True)
        success = await self.info_manager.set_spawn(x, y, z)
        
        if success:
            await interaction.followup.send(f"✅ Spawn set to X:{x}, Y:{y}, Z:{z}. Channel updated.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to update config.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
