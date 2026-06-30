import discord
from discord import app_commands
from discord.ext import commands
import os
import re
import time
import psutil
import asyncio
from datetime import timedelta
from src.config import config
from src.utils import rcon_cmd, has_role, parse_server_version, get_server_mod_folder, get_dir_size_gb
from src.logger import logger
from src.server_info_manager import ServerInfoManager

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.info_manager = ServerInfoManager(bot)

    def _get_player_list_info(self, rcon_response: str) -> tuple[str, str, str]:
        """
        Parses the RCON 'list' command response to extract player information.
        Returns a tuple: (formatted_player_list_string, current_players_count_str, max_players_count_str)
        """
        RCON_DOWN_MSG = "Unable to fetch player list"

        if not rcon_response or rcon_response == RCON_DOWN_MSG:
            # RCON Down Fallback: Use LogWatcher's memory from config
            try:
                bot_cfg = config.load_bot_config()
                players = bot_cfg.get('online_players', [])
                if not players:
                    return "No players online (RCON down)", "0", "?"
                
                players_formatted = f"**{len(players)} players online** (via logs)\n" + "\n".join([f"👤 {n}" for n in players])
                return players_formatted, str(len(players)), "?"
            except Exception:
                return f"```{rcon_response or 'RCON Timeout'}```", "?", "?"

        match = re.search(r"There are (\d+) of a max of (\d+) players online:(.*)", str(rcon_response))
        if match:
            count_str, max_str, names_str = match.groups()
            current_players_count = count_str
            max_players_count = max_str
            if count_str == "0":
                players_formatted = f"No players online (0/{max_str})"
            else:
                names = [n.strip() for n in names_str.split(",") if n.strip()]
                players_formatted = f"**{count_str}/{max_str} players online**\n" + "\n".join([f"👤 {n}" for n in names])
            return players_formatted, current_players_count, max_players_count
        else:
            # Fallback if regex doesn't match
            # Try to extract counts even if names list is malformed
            numbers = re.findall(r'\d+', rcon_response)
            current_players_count = numbers[-2] if len(numbers) >= 2 else "?"
            max_players_count = numbers[-1] if len(numbers) >= 2 else "?"
            return f"```{rcon_response}```", current_players_count, max_players_count

    async def _get_tps_info(self) -> str:
        """
        Fetches and parses TPS information from the Minecraft server using RCON.
        Attempts Paper/Forge direct TPS, then falls back to Vanilla debug profiling.
        """
        tps = "Unknown"
        try:
            # Attempt Paper/Forge direct TPS fetch
            try:
                 success_tps, tps_raw = await rcon_cmd("tps")
                 # Usually returns "TPS from last 1m, 5m, 15m: 20.0, 20.0, 20.0"
                 if success_tps and "TPS from last" in tps_raw:
                     tps = tps_raw.split(":")[-1].strip().split(",")[0].strip()
                     tps = re.sub(r'§.', '', tps) # Strip Minecraft color codes
                 else:
                     raise ValueError("Not a valid TPS string")
            except Exception:
                 # Vanilla Fallback: Use debug start/stop to infer TPS
                 _, _ = await rcon_cmd("debug start")
                 await asyncio.sleep(1.0) # wait exactly 1 second
                 success_debug, debug_raw = await rcon_cmd("debug stop")
                 
                 if success_debug and "Stopped tick profiling after" in debug_raw:
                     # Sample: "Stopped tick profiling after 1 seconds and 20 ticks (20.00 ticks per second)"
                     match = re.search(r'\(([\d.]+)\s+ticks per second\)', debug_raw)
                     if match:
                         tps = match.group(1)
                     else:
                         tps = "N/A (Vanilla)"
                 else:
                     tps = "N/A (Vanilla)"
        except Exception as e:
            logger.debug(f"TPS check failed: {e}")
            tps = "N/A"
        return tps

    @app_commands.command(name="uptime", description="Check how long the bot and server have been running")
    @has_role("status")
    async def uptime(self, interaction: discord.Interaction):
        """Displays uptime for both the bot and the Minecraft server."""
        await interaction.response.defer(ephemeral=True)
        
        # Bot Uptime
        bot_uptime_sec = int(time.time() - self.bot.start_time)
        bot_uptime = str(timedelta(seconds=bot_uptime_sec))
        
        # Server Uptime
        server_uptime = "Offline 🔴"
        if self.bot.server.is_running():
            start_time = self.bot.server.get_start_time()
            if start_time:
                server_uptime_sec = int(time.time() - start_time)
                server_uptime = f"**{str(timedelta(seconds=server_uptime_sec))}** 🟢"
            else:
                server_uptime = "Online (Unknown duration) 🟢"
        
        embed = discord.Embed(title="⏲️ System Uptime", color=0x5865F2)
        embed.add_field(name="Discord Bot", value=f"**{bot_uptime}**", inline=False)
        embed.add_field(name="Minecraft Server", value=server_uptime, inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="players", description="List online players")
    @has_role("players")
    async def players(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not self.bot.server.is_running():
                embed = discord.Embed(description="🔴 Server is offline.", color=0xED4245)
                await interaction.followup.send(embed=embed)
                return
            
            try:
                success, res = await rcon_cmd("list")
                description, _, _ = self._get_player_list_info(res)

                embed = discord.Embed(title="Online Players", description=description, color=0x5865F2)
                await interaction.followup.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to get player list: {e}")
                embed = discord.Embed(description="❌ Failed to get player list.", color=0xED4245)
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in players command: {e}", exc_info=True)
            try:
                await interaction.followup.send("❌ Failed to get players.")
            except Exception as send_error:
                logger.debug(f"Failed to send players error message: {send_error}")

    @app_commands.command(name="version", description="Show server version")
    @has_role("version")
    async def version(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            ver = await parse_server_version()
            await interaction.followup.send(f"🛠️ Server version: {ver}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in version command: {e}", exc_info=True)
            try:
                await interaction.followup.send("❌ Failed to get server version.", ephemeral=True)
            except Exception as send_error:
                logger.debug(f"Failed to send version error message: {send_error}")

    @app_commands.command(name="seed", description="Displays the server seed")
    @has_role("seed")
    async def seed(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            seed = await self.info_manager._get_seed()
            
            if seed and seed != 'Random/Hidden':
                await interaction.followup.send(f"🌱 Seed: {seed}")
                return
            
            if self.bot.server.is_running():
                try:
                    success, seed_val = await rcon_cmd("seed")
                    await interaction.followup.send(f"🌱 {seed_val}")
                    return
                except Exception as rcon_error:
                    logger.debug(f"Seed RCON fallback failed: {rcon_error}")
            
            await interaction.followup.send("🌱 Seed: Random/Hidden (not set in server.properties)")

        except Exception as e:
            logger.error(f"Error in seed command: {e}", exc_info=True)
            await interaction.followup.send("❌ Failed to get seed.", ephemeral=True)

    @app_commands.command(name="mods", description="Lists installed mods")
    @has_role("mods")
    async def mods(self, interaction: discord.Interaction):
        try:
            folder_name = await get_server_mod_folder()
            if folder_name is None:
                await interaction.response.send_message("❌ Vanilla servers do not support mods or plugins.", ephemeral=True)
                return
                
            mods_dir = os.path.join(config.SERVER_DIR, folder_name)
            exists = await asyncio.to_thread(os.path.exists, mods_dir)
            if not exists:
                await interaction.response.send_message(f"❌ {folder_name.capitalize()} folder not found.", ephemeral=True)
                return
            try:
                mods_list = [f for f in await asyncio.to_thread(os.listdir, mods_dir) if f.endswith('.jar')]
                if not mods_list:
                    await interaction.response.send_message(f"🧩 No {folder_name} installed.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"🧩 Installed {folder_name}:\n- " + "\n- ".join(mods_list), ephemeral=True)
            except OSError as e:
                logger.error(f"Failed to list {folder_name} directory: {e}")
                await interaction.response.send_message(f"❌ Failed to read {folder_name} directory.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in mods command: {e}", exc_info=True)
            try:
                await interaction.response.send_message("❌ Failed to get mods list.", ephemeral=True)
            except Exception as send_error:
                logger.debug(f"Failed to send mods error message: {send_error}")

    async def build_info_embed(self, guild: discord.Guild = None) -> discord.Embed:
        """Shared method to build the /info embed for broadcasting or command usage."""
        await self.info_manager.update_info(guild)
        ver = await parse_server_version()
        
        ip = "Unknown (Check /ip)"
        if config.CUSTOM_IP:
            ip = config.CUSTOM_IP
        else:
            try:
                playit_cog = self.bot.get_cog("PlayitCog")
                if playit_cog and playit_cog.cached_address:
                    ip = playit_cog.cached_address
                else:
                    bot_cfg = config.load_bot_config()
                    ip = bot_cfg.get('playit_ip', "Unknown (Check /ip)")
            except Exception as e:
                logger.error(f"Failed to fetch IP for info command: {e}")
        
        spawn = self.info_manager._get_spawn() or "Not set"
        
        # Fetch Seed
        seed = await self.info_manager._get_seed()
        if not seed or seed == 'Random/Hidden':
            if self.bot.server.is_running():
                try:
                    success, seed_val = await rcon_cmd("seed")
                    if success:
                        seed = seed_val
                except Exception:
                    pass
        if not seed:
            seed = "Unknown"
        elif seed.startswith("Seed: "):
            seed = seed[6:]
        elif seed.startswith("[") and "]" in seed:
            # e.g. [12345] -> 12345
            seed = seed.strip("[]")
        
        # World Size
        world_size = "Unknown"
        try:
            world_dir = os.path.join(config.SERVER_DIR, "world")
            if os.path.exists(world_dir):
                size_gb = await get_dir_size_gb(world_dir)
                world_size = f"{size_gb:.2f} GB"
            else:
                # Fallback to entire server dir if world isn't found
                size_gb = await get_dir_size_gb(config.SERVER_DIR)
                world_size = f"{size_gb:.2f} GB (Total)"
        except Exception as e:
            logger.debug(f"Failed to get world size: {e}")
        
        # Uptime (Bot)
        bot_uptime_sec = int(time.time() - self.bot.start_time)
        bot_uptime = str(timedelta(seconds=bot_uptime_sec))
        
        embed = discord.Embed(
            title="📊 Server Dashboard",
            description=f"🌐 **IP Address:** `{ip}`",
            color=0x2b2d31 # A sleek dark theme color often used in Discord
        )
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Server Status & Info
        if self.bot.server.is_running():
            server_uptime_str = "Unknown"
            if hasattr(self.bot.server, 'get_start_time'):
                start_time = self.bot.server.get_start_time()
                if start_time:
                    delta = timedelta(seconds=int(time.time() - start_time))
                    server_uptime_str = str(delta)
            
            tps = await self._get_tps_info()
            
            try:
                # Fix: rcon_cmd returns (success, response)
                success_list, players_raw = await rcon_cmd("list")
                players_formatted, current_players, max_players = self._get_player_list_info(players_raw)
            except Exception as e:
                logger.error(f"Error fetching player list for info command: {e}")
                players_formatted, current_players, max_players = self._get_player_list_info("Unable to fetch player list")
            
            embed.add_field(name="🟢 Server Status", value="`Online`", inline=True)
            embed.add_field(name="🛠️ Version", value=f"`{ver}`", inline=True)
            embed.add_field(name="⏱️ TPS", value=f"`{tps}`", inline=True)
            
            embed.add_field(name="👥 Players", value=f"`{current_players}/{max_players}`", inline=True)
            embed.add_field(name="⏳ Server Uptime", value=f"`{server_uptime_str}`", inline=True)
            embed.add_field(name="🤖 Bot Uptime", value=f"`{bot_uptime}`", inline=True)
        else:
            embed.add_field(name="🔴 Server Status", value="`Offline`", inline=True)
            embed.add_field(name="🛠️ Version", value=f"`{ver}`", inline=True)
            embed.add_field(name="🤖 Bot Uptime", value=f"`{bot_uptime}`", inline=True)
        
        # Performance & Resources
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        embed.add_field(name="💻 System CPU", value=f"`{cpu_percent}%`", inline=True)
        embed.add_field(name="🧠 System RAM", value=f"`{mem.percent}% ({mem.used // 1024**3}GB/{mem.total // 1024**3}GB)`", inline=True)
        embed.add_field(name="💾 World Size", value=f"`{world_size}`", inline=True)
        
        # Side-by-side fields for Spawn and Seed
        embed.add_field(name="📍 Spawn", value=f"`{spawn}`", inline=True)
        embed.add_field(name="🌱 Seed", value=f"`{seed}`", inline=True)
        
        if self.bot.user and self.bot.user.avatar:
            embed.set_footer(text="Minecraft Server Manager", icon_url=self.bot.user.avatar.url)
        else:
            embed.set_footer(text="Minecraft Server Manager")
            
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(name="info", description="Show technical bot information")
    @has_role("server_info")
    async def info(self, interaction: discord.Interaction):
        """Displays detailed server information"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.build_info_embed(interaction.guild)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in info command: {e}", exc_info=True)
            await interaction.followup.send("❌ Failed to get info.", ephemeral=True)

    @app_commands.command(name="set_spawn", description="Set spawn coordinates for server info")
    @app_commands.describe(x="X coordinate", y="Y coordinate", z="Z coordinate")
    @has_role("set_spawn")
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
