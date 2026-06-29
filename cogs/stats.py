
import discord
from discord import app_commands
from discord.ext import commands
import os
import aiohttp
import nbtlib
import asyncio
import uuid # Moved from get_offline_uuid
from src.config import config
from src.utils import has_role, get_uuid # Standardized import
from src.logger import logger
from src.mc_link_manager import MCLinkManager

# --- Constants ---
TICKS_PER_SECOND = 20
SECONDS_PER_HOUR = 3600

class StatsCog(commands.Cog):
    """
    Handles player statistics and profile commands.

    Provides commands to view Minecraft player stats, including playtime,
    kills, and deaths, with support for both premium and cracked accounts.
    """
    def __init__(self, bot):
        """Initializes the StatsCog with the bot instance."""
        self.bot = bot

    # --- Data Fetching Helpers ---

    async def get_uuid_online(self, username: str):
        """
        Fetches UUID and official name from Mojang API.

        Used for legitimate (premium) accounts to get accurate skins and IDs.

        Args:
            username (str): The Minecraft username to look up.

        Returns:
            tuple[str | None, str | None]: A tuple containing (uuid, official_name).
        """
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f'https://api.mojang.com/users/profiles/minecraft/{username}') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('id'), data.get('name')
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            logger.warning(f"Mojang API request failed for '{username}': {e}")
        return None, None

    async def get_offline_uuid(self, username: str):
        """
        Generates an offline UUID (v3) based on the username.

        Args:
            username (str): The Minecraft username to generate a UUID for.

        Returns:
            tuple[str, str]: A tuple containing (uuid_string, username).
        """
        offline_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}")).replace('-', '')
        return offline_uuid, username

    def get_stats_from_nbt(self, uuid_str: str, server_path: str):
        """
        Parses player statistics from local server files.

        1. Reads world/stats/<uuid>.json for standard stats.
        2. Reads world/playerdata/<uuid>.dat using nbtlib for additional data.

        Args:
            uuid_str (str): The Minecraft UUID of the player.
            server_path (str): The path to the Minecraft server directory.

        Returns:
            tuple[dict, dict]: A tuple containing (stats_json, nbt_data).
        """
        # Format UUID with dashes using uuid.UUID object
        formatted_uuid = str(uuid.UUID(uuid_str))
        
        # Use config.WORLD_FOLDER which dynamically reads from server.properties
        world_path = os.path.join(server_path, config.WORLD_FOLDER) 
        
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

        # 2. Try playerdata .dat file (NBT) for other info
        player_dat = os.path.join(world_path, 'playerdata', f"{formatted_uuid}.dat")
        nbt_data = {}
        if os.path.exists(player_dat):
            try:
                nbt_file = nbtlib.load(player_dat)
                nbt_data = nbt_file.root
            except Exception as e:
                logger.error(f"Failed to load user NBT: {e}")
        
        return stats, nbt_data

    # --- Commands ---

    @app_commands.command(name="stats", description="Get player statistics")
    @app_commands.describe(player="Minecraft username", user="Discord user")
    @has_role("stats")
    async def stats(self, interaction: discord.Interaction, player: str = None, user: discord.Member = None):
        """
        Displays statistics for a Minecraft player.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
            player (str, optional): The Minecraft username to look up.
            user (discord.Member, optional): The Discord user to look up.
        """
        await interaction.response.defer()
        
        # Default to the commanding user if no arguments are provided
        if not player and not user:
            user = interaction.user

        link_manager = MCLinkManager()
        server_path = config.SERVER_DIR
        
        target_name = player
        resolved_uuid = None
        is_cracked = False
        is_premium = False

        if user:
            link = await link_manager.get_link_by_discord(user.id)
            if link:
                target_name = link.get('mc_username')
                is_premium = link.get('is_premium', False)
                is_cracked = not is_premium
            else:
                await interaction.followup.send("❌ This user is not linked to a Minecraft player.")
                return
        elif player:
            # Check if this player name is linked to anyone in our links
            link = await link_manager.get_link_by_mc(player)
            if link:
                target_name = link.get('mc_username')
                is_premium = link.get('is_premium', False)
                is_cracked = not is_premium
            else:
                # Not linked, but they specified a player name.
                # Try Mojang to check if they are premium
                uuid_online, name_online = await self.get_uuid_online(player)
                if uuid_online:
                    target_name = name_online
                    is_premium = True
                    is_cracked = False
                else:
                    target_name = player
                    is_premium = False
                    is_cracked = True

        if not target_name:
            await interaction.followup.send("❌ Could not determine target player name.")
            return

        # Look up actual UUID in the server's usercache.json (since the server knows the actual UUID it uses)
        cached_uuid = await get_uuid(target_name)
        if cached_uuid:
            resolved_uuid = cached_uuid
        else:
            # Fallback to generating the offline UUID (since the server runs in offline-mode)
            offline_uuid, _ = await self.get_offline_uuid(target_name)
            resolved_uuid = offline_uuid

        # Load data in executor to avoid blocking
        stats_json, nbt_data = await asyncio.to_thread(self.get_stats_from_nbt, resolved_uuid, server_path)
        
        if not stats_json and not nbt_data:
             await interaction.followup.send(f"❌ No data found for player '{target_name}'. Has this player joined the server?")
             return

        # Process stats
        play_time_ticks = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:play_time', 0)
        deaths = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:deaths', 0)
        player_kills = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:player_kills', 0)
        mob_kills = stats_json.get('stats', {}).get('minecraft:custom', {}).get('minecraft:mob_kills', 0)
        
        hours = play_time_ticks / TICKS_PER_SECOND / SECONDS_PER_HOUR
        
        # Skin: if premium, fetch their premium UUID from Mojang for the skin.
        # Otherwise, use Steve skin.
        skin_url = "https://minecraft-heads.com/avatar/Steve/64"
        if is_premium:
            skin_uuid, _ = await self.get_uuid_online(target_name)
            if skin_uuid:
                skin_url = f"https://crafatar.com/avatars/{skin_uuid}?overlay"

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
