
import discord
from discord import app_commands
from discord.ext import commands
import os
import aiohttp
import nbtlib
import asyncio
from src.config import config
from src.utils import has_role, map_key, display_key
from src.logger import logger

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_uuid_online(self, username: str):
        """
        Fetches UUID from Mojang API.
        Used for legitimate (premium) accounts to get accurate skins and IDs.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.mojang.com/users/profiles/minecraft/{username}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('id'), data.get('name')
        return None, None

    async def get_offline_uuid(self, username: str):
        """Generate offline UUID (v3) based on the username."""
        import uuid
        return str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}")).replace('-', ''), username

    def get_stats_from_nbt(self, uuid_str: str, server_path: str):
        """
        Parses player statistics from local server files.
        1. Reads world/stats/<uuid>.json for standard stats.
        2. Reads world/playerdata/<uuid>.dat using nbtlib for additional data.
        Falls back gracefully if files are missing (e.g. new player).
        """
        # Formatted UUID (with dashes)
        formatted_uuid = f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:]}"
        
        bot_config = config.load_bot_config()
        # Assume world folder is 'world' or get from config if we had it. defaulting to 'world'
        world_path = os.path.join(server_path, 'world') 
        
        # 1. Try generic stats.json first (standard vanilla stats)
        stats_file = os.path.join(world_path, 'stats', f"{formatted_uuid}.json")
        stats = {}
        if os.path.exists(stats_file):
             import json
             try:
                 with open(stats_file, 'r') as f:
                     stats = json.load(f)
             except Exception as e:
                 logger.error(f"Failed to load stats json: {e}")

        # 2. Try playerdata .dat file (NBT) for other info like inventory, pos, or legacy stats?
        # User specifically mentioned "legit/offline players -> parse .dat file".
        # And "NBT Parse: nbtlib.load(...) -> root['bukkit']['lastPlayed']"
        player_dat = os.path.join(world_path, 'playerdata', f"{formatted_uuid}.dat")
        nbt_data = {}
        if os.path.exists(player_dat):
            try:
                nbt_file = nbtlib.load(player_dat)
                nbt_data = nbt_file.root
            except Exception as e:
                logger.error(f"Failed to load user NBT: {e}")
        
        return stats, nbt_data

    @app_commands.command(name="stats", description="Get player statistics")
    @app_commands.describe(player="Minecraft username or Discord user")
    async def stats(self, interaction: discord.Interaction, player: str = None, user: discord.Member = None):
        await interaction.response.defer()
        
        bot_config = config.load_bot_config()
        server_path = config.SERVER_DIR
        
        target_name = player
        uuid = None
        is_cracked = False

        if user:
            # Look up in mappings
            mapping = bot_config.get('mappings', {}).get(str(user.id))
            if mapping:
                uuid = mapping.get('uuid')
                target_name = mapping.get('name')
                is_cracked = mapping.get('cracked', False)
            else:
                await interaction.followup.send("❌ This user is not linked to a Minecraft player.")
                return
        elif player:
            # Try to determine if online or offline based on existing files or config
            # For now, let's try Mojang first, then fallback to offline UUID if not found or if server is 'cracked' mode?
            # User request: "Legit players -> Mojang API... Offline players -> parse .dat"
            
            # Check mappings first
            # Reverse lookup?
            found_map = False
            for uid, data in bot_config.get('mappings', {}).items():
                if data.get('name', '').lower() == player.lower():
                    uuid = data.get('uuid')
                    is_cracked = data.get('cracked', False)
                    target_name = data.get('name')
                    found_map = True
                    break
            
            if not found_map:
                # Try Mojang
                uuid, name = await self.get_uuid_online(player)
                if uuid:
                     target_name = name
                     is_cracked = False
                else:
                     # Fallback to offline UUID
                     uuid, name = await self.get_offline_uuid(player)
                     target_name = name
                     is_cracked = True

        if not uuid:
            await interaction.followup.send(f"❌ Could not find player '{player}'.")
            return

        # Load data
        # Run in executor to avoid blocking
        stats_json, nbt_data = await asyncio.to_thread(self.get_stats_from_nbt, uuid, server_path)
        
        if not stats_json and not nbt_data:
             await interaction.followup.send(f"❌ No data found for player '{target_name}'. Has this player joined the server?")
             return

        # Process stats
        # Playtime: stored in 'minecraft:custom' -> 'minecraft:play_time' (ticks) in JSON
        # Or 'bukkit' -> 'lastPlayed' in NBT (timestamp)
        
        play_time_ticks = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:play_time', 0)
        deaths = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:deaths', 0)
        player_kills = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:player_kills', 0)
        mob_kills = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:mob_kills', 0)
        
        hours = play_time_ticks / 20 / 3600
        
        # Skin
        if is_cracked:
            skin_url = "https://minecraft-heads.com/scripts/3d-head.php?hrh=00&aa=true&headOnly=true&ratio=6" # Generic steve or dynamic?
            # User suggested: https://minecraft-heads.com/avatar/Steve/64
            skin_url = "https://minecraft-heads.com/avatar/Steve/64"
        else:
            skin_url = f"https://crafatar.com/avatars/{uuid}?overlay"

        embed = discord.Embed(title=f"Stats for {target_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=skin_url)
        embed.add_field(name="Playtime", value=f"{hours:.2f} hours", inline=True)
        embed.add_field(name="Deaths", value=str(deaths), inline=True)
        embed.add_field(name="Player Kills", value=str(player_kills), inline=True)
        embed.add_field(name="Mob Kills", value=str(mob_kills), inline=True)
        
        if is_cracked:
            embed.set_footer(text="Account Type: Cracked / Offline")
        else:
            embed.set_footer(text="Account Type: Premium")

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StatsCog(bot))
