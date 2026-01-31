import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import aiofiles
from src.config import config
from src.utils import rcon_cmd, get_uuid, display_key, map_key, has_role, parse_server_version

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="status", description="Show Minecraft server status")
    @has_role("status")
    async def status(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Minecraft Server Status")
        if self.bot.server.is_running():
            embed.color = 0x57F287 # Green
            players_response = await rcon_cmd("list")
            embed.add_field(name="Status", value="🟢 **Online**", inline=False)
            embed.add_field(name="Players", value=f"```{players_response}```", inline=False)
        else:
            embed.color = 0xED4245 # Red
            embed.add_field(name="Status", value="🔴 **Offline**", inline=False)
        
        from datetime import datetime
        embed.set_footer(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="players", description="List online players")
    @has_role("players")
    async def players(self, interaction: discord.Interaction):
        if not self.bot.server.is_running():
            embed = discord.Embed(description="🔴 Server is offline.", color=0xED4245)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        res = await rcon_cmd("list")
        embed = discord.Embed(title="Online Players", description=f"```{res}```", color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="version", description="Show server version")
    @has_role("version")
    async def version(self, interaction: discord.Interaction):
        ver = await parse_server_version()
        await interaction.response.send_message(f"🛠️ Server version: {ver}", ephemeral=True)

    @app_commands.command(name="seed", description="Displays the server seed")
    @has_role("seed")
    async def seed(self, interaction: discord.Interaction):
        try:
             seed_val = await rcon_cmd("seed")
             await interaction.response.send_message(f"🌱 {seed_val}", ephemeral=True)
        except Exception as e:
             await interaction.response.send_message(f"❌ Failed to get seed: {e}", ephemeral=True)

    @app_commands.command(name="mods", description="Lists installed mods")
    @has_role("mods")
    async def mods(self, interaction: discord.Interaction):
        mods_dir = os.path.join(config.SERVER_DIR, 'mods')
        exists = await asyncio.to_thread(os.path.exists, mods_dir)
        if not exists:
             await interaction.response.send_message("❌ Mods folder not found.", ephemeral=True)
             return
        mods_list = [f for f in await asyncio.to_thread(os.listdir, mods_dir) if f.endswith('.jar')]
        if not mods_list:
             await interaction.response.send_message("🧩 No mods installed.", ephemeral=True)
        else:
             await interaction.response.send_message(f"🧩 Installed mods:\n- " + "\n- ".join(mods_list), ephemeral=True)

    @app_commands.command(name="server_info", description="Displays server information")
    @has_role("server_info")
    async def server_info(self, interaction: discord.Interaction):
          ver = await parse_server_version()
          players_res = await rcon_cmd("list")
          seed_res = await rcon_cmd("seed")
          
          embed = discord.Embed(title="Server Information")
          embed.add_field(name="Version", value=ver, inline=False)
          embed.add_field(name="Players", value=players_res, inline=False)
          embed.add_field(name="Seed", value=seed_res, inline=False)
          
          if not interaction.response.is_done():
               await interaction.response.send_message(embed=embed, ephemeral=True)
          else:
               await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
