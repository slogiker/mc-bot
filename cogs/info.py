import discord
from discord import app_commands
from discord.ext import commands
import os
import json
from src.config import config
from src.utils import rcon_cmd, get_uuid, display_key, map_key

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="status", description="Show Minecraft server status")
    async def status(self, interaction: discord.Interaction):
        # TODO: Add cooldown check
        
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
    async def players(self, interaction: discord.Interaction):
        if not self.bot.server.is_running():
            embed = discord.Embed(description="🔴 Server is offline.", color=0xED4245)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        res = await rcon_cmd("list")
        embed = discord.Embed(title="Online Players", description=f"```{res}```", color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="version", description="Show server version")
    async def version(self, interaction: discord.Interaction):
        # Logic to extract version from logs or rcon
        # For now, just a placeholder or reading from properties/logs
        await interaction.response.send_message("Server version check not implemented yet.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
