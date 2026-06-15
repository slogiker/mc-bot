import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import os
import re
import time
import psutil
import subprocess
from src.config import config
from src.logger import logger
from src.utils import has_role

# Cache expires after 2 hours (7200 seconds)
CACHE_TTL = 7200

class PlayitCog(commands.Cog):
    """
    Manages Playit.gg integration details.
    Allows retrieving the public connection address and claiming new tunnels.
    """
    def __init__(self, bot):
        self.bot = bot
        self.cached_address = None
        self.cache_time = None
        self.tunnels = []
        self._current_claim_code = None
        self._claim_link = None
        
        # Load from config if available
        bot_cfg = config.load_bot_config()
        self.cached_address = bot_cfg.get('playit_ip')
        if self.cached_address:
            self.tunnels = [self.cached_address]
            self.cache_time = time.time()
            
        # Try to refresh/start in background
        asyncio.create_task(self._initial_setup())

    async def _initial_setup(self):
        """Initial tunnel check and startup."""
        await asyncio.sleep(5)
        secret_key = self.get_secret_key()
        
        if not secret_key:
            logger.info("Playit: No secret key found. Starting in 'unclaimed' mode...")
            await self.start_tunnel()
        else:
            await self._initial_fetch()

    async def _initial_fetch(self):
        """Fetch IP with existing key."""
        address, _ = await self.fetch_playit_address()
        if address:
            self.cached_address = address
            self.cache_time = time.time()
            self.tunnels = [address]
            with config.update_bot_config() as data:
                data['playit_ip'] = address
            logger.info(f"Playit IP address updated: {address}")
            
            # Trigger server info update so #server-information is accurate
            try:
                from src.server_info_manager import ServerInfoManager
                await ServerInfoManager(self.bot).update_info()
            except Exception as e:
                logger.error(f"Failed to update info after IP fetch: {e}")

    def get_secret_key(self):
        """Get Playit secret key from data file."""
        key_path = os.path.join("data", "playit_secret.key")
        if os.path.exists(key_path):
            try:
                with open(key_path, "r") as f:
                    key = f.read().strip()
                    return key if key else None
            except Exception as e:
                logger.error(f"Failed to read playit secret key: {e}")
        
        # Fallback to env
        env_key = os.environ.get("PLAYIT_SECRET_KEY", "").strip()
        return env_key if env_key else None

    async def start_tunnel(self):
        """Starts or restarts the playit tunnel."""
        logger.info("Playit: Starting tunnel...")
        secret_key_path = os.path.join("data", "playit_secret.key")
        socket_path = os.path.join("data", "playit.sock")
        log_path = os.path.join("logs", "playit.log")

        # Kill existing if any
        await asyncio.create_subprocess_shell("tmux kill-session -t playit", stderr=asyncio.subprocess.DEVNULL)
        
        # Build command
        cmd = ["playit", "--platform-docker", "--socket-path", socket_path, "-l", log_path]
        secret_key = self.get_secret_key()
        if secret_key:
            # Write key to file if it came from env but file is missing
            if not os.path.exists(secret_key_path):
                with open(secret_key_path, "w") as f:
                    f.write(secret_key)
            cmd.extend(["--secret-path", secret_key_path])

        # Start in tmux
        start_cmd = f"tmux new-session -d -s playit '{' '.join(cmd)}'"
        proc = await asyncio.create_subprocess_shell(start_cmd)
        await proc.wait()

    def _is_cache_valid(self):
        """Check if cached address is still valid (within TTL)."""
        if self.cached_address and self.cache_time:
            return (time.time() - self.cache_time) < CACHE_TTL
        return False

    @app_commands.command(name="status", description="Show detailed bot and server status")
    @has_role("status")
    async def status_combined(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # 1. Gather Data
        is_running = self.bot.server.is_running()
        is_stopped = self.bot.server.is_intentionally_stopped()
        
        # IP Address
        address, _ = await self.fetch_playit_address()
        if not address:
            if not self.get_secret_key():
                address = "🟡 Unclaimed (Use /playit claim)"
            else:
                address = "🔴 Error fetching address"

        # Minecraft Status & Color
        if is_running:
            mc_status = "🟢 **Online**"
            embed_color = discord.Color.green()
        elif is_stopped:
            mc_status = "⚪ **Stopped (Intentionally)**"
            embed_color = discord.Color.light_grey()
        else:
            mc_status = "⚠️ **Crashed / Offline**"
            embed_color = discord.Color.red()

        # Build Status Embed
        embed = discord.Embed(title="🖥️ Server Status", color=embed_color)
        
        # IP at the top
        embed.add_field(name="🌍 Public Address", value=f"`{address}`", inline=False)
        
        # Minecraft Status
        embed.add_field(name="🎮 Minecraft", value=mc_status, inline=True)

        # Uptime
        uptime_str = "Offline"
        if is_running:
            start_time = self.bot.server.get_start_time()
            if start_time:
                from datetime import timedelta
                delta = timedelta(seconds=int(time.time() - start_time))
                uptime_str = f"**{str(delta).split('.')[0]}**" # Remove milliseconds
            else:
                uptime_str = "Unknown"
        embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)

        # World Size
        from src.utils import get_dir_size_gb
        world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
        world_size = await get_dir_size_gb(world_path)
        embed.add_field(name="📂 World Size", value=f"**{world_size:.2f} GB**", inline=True)

        # Players List
        if is_running:
            from src.utils import rcon_cmd
            success, response = await rcon_cmd("list")
            if success:
                # Basic parsing: 'There are 0 of a max of 20 players online:'
                # or 'There are 1 of a max of 20 players online: Slogiker'
                if ":" in response:
                    count_part, names_part = response.split(":", 1)
                    players_list = names_part.strip() or "None"
                    count = count_part.split(" ")[2]
                    max_players = count_part.split(" ")[5]
                    players_val = f"**{count}/{max_players}**\n{players_list}"
                else:
                    players_val = f"```{response}```"
            else:
                players_val = "```Unable to fetch player list (RCON)```"
            
            embed.add_field(name="👥 Online Players", value=players_val, inline=False)

        await interaction.followup.send(embed=embed)

    playit_group = app_commands.Group(name="playit", description="Playit.gg tunnel management")

    @playit_group.command(name="claim", description="Generate a new Playit.gg claim link")
    @has_role("admin")
    async def playit_claim(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Ensure daemon is running first
        await self.start_tunnel()
        await asyncio.sleep(2)
        
        socket_path = os.path.join("data", "playit.sock")
        
        try:
            # 1. Generate code
            proc = await asyncio.create_subprocess_exec(
                "playit-cli", "--socket-path", socket_path, "claim", "generate",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return await interaction.followup.send(f"❌ Failed to generate claim code: {stderr.decode()}")
            
            code = stdout.decode().strip()
            self._current_claim_code = code

            # 2. Generate URL
            proc = await asyncio.create_subprocess_exec(
                "playit-cli", "--socket-path", socket_path, "claim", "url", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return await interaction.followup.send(f"❌ Failed to generate claim URL: {stderr.decode()}")
            
            url = stdout.decode().strip()
            self._claim_link = url

            await interaction.followup.send(
                f"🔗 **Playit Claim Link**: {url}\n\n"
                "1. Click the link and claim the agent in your Playit account.\n"
                "2. **IMPORTANT**: Keep the bot running while you do this!\n"
                "3. Once done, return here and run **`/playit verify`**.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in /playit claim: {e}")
            await interaction.followup.send(f"❌ Unexpected error: {e}")

    @playit_group.command(name="verify", description="Verify and exchange your claim code for a secret key")
    @has_role("admin")
    async def playit_verify(self, interaction: discord.Interaction):
        if not self._current_claim_code:
            return await interaction.response.send_message("❌ No active claim process. Run `/playit claim` first.", ephemeral=True)
        
        await interaction.response.send_message("🔄 Verifying claim and exchanging for secret key...", ephemeral=True)
        
        socket_path = os.path.join("data", "playit.sock")
        
        try:
            # Exchange code for secret
            proc = await asyncio.create_subprocess_exec(
                "playit-cli", "--socket-path", socket_path, "claim", "exchange", self._current_claim_code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return await interaction.followup.send(
                    f"❌ Exchange failed: {stderr.decode()}\n"
                    "Make sure you clicked the link and confirmed it on Playit.gg first!",
                    ephemeral=True
                )
            
            secret = stdout.decode().strip()
            if not secret:
                return await interaction.followup.send("❌ Received empty secret key from Playit.", ephemeral=True)

            # Save secret
            key_path = os.path.join("data", "playit_secret.key")
            with open(key_path, "w") as f:
                f.write(secret)
            
            await interaction.followup.send("✅ Secret key saved! Restarting tunnel...", ephemeral=True)
            await self.start_tunnel()
            
            # Final check
            await asyncio.sleep(5)
            address, _ = await self.fetch_playit_address()
            if address:
                await interaction.followup.send(f"🚀 **Tunnel Online!** Public IP: `{address}`", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Tunnel started, but IP is still initializing. Check `/ip` in a minute.", ephemeral=True)
                
            # Clear state
            self._current_claim_code = None
            self._claim_link = None

        except Exception as e:
            logger.error(f"Error in /playit verify: {e}")
            await interaction.followup.send(f"❌ Unexpected error during verification: {e}", ephemeral=True)

    @playit_group.command(name="restart", description="Restart the Playit tunnel")
    @has_role("admin")
    async def playit_restart(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔄 Restarting Playit tunnel...", ephemeral=True)
        await self.start_tunnel()
        await asyncio.sleep(5)
        address, _ = await self.fetch_playit_address()
        if address:
            await interaction.followup.send(f"✅ Playit restarted! New IP: `{address}`", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Playit restarted but IP is still unknown. It may take a minute.", ephemeral=True)

    @app_commands.command(name="ip", description="Get the public Playit.gg address")
    @has_role("status")
    async def get_ip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        if self._is_cache_valid():
            await interaction.followup.send(f"🌍 **Public Address**: `{self.cached_address}`")
            return
        address, error = await self.fetch_playit_address()
        if address:
            self.cached_address = address
            self.cache_time = time.time()
            self.tunnels = [address]
            await interaction.followup.send(f"🌍 **Public Address**: `{address}`")
        else:
            await interaction.followup.send(error)

    async def fetch_playit_address(self):
        """
        Fetches the tunnel address via Playit REST API.
        Checks for the secret key file dynamically to ensure consistency.
        """
        secret_key = self.get_secret_key()
        if not secret_key:
            # If the file is gone, clear any stale cached address immediately
            self.cached_address = None
            self.tunnels = []
            return None, "❌ No Playit secret key found. Run `/playit claim` to set one up."

        url = "https://api.playit.gg/v1/agents/rundata"
        headers = {"Authorization": f"Agent-Key {secret_key}", "Content-Type": "application/json"}
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json={}) as resp:
                    if resp.status == 401:
                        logger.error(f"Playit API 401 Unauthorized. Key length: {len(secret_key)}. First 4 chars: {secret_key[:4]}... Last 4: ...{secret_key[-4:]}")
                        return None, "❌ Playit rejected the secret key (401 Unauthorized)."
                    if resp.status != 200:
                        return None, f"❌ Playit API error ({resp.status})."
                    data = await resp.json()
                    tunnels = data.get("data", {}).get("tunnels", [])
                    if not tunnels:
                        return None, "❌ No tunnels configured."
                    for tunnel in tunnels:
                        if tunnel.get("tunnel_type") == "minecraft-java":
                            return tunnel["display_address"], None
                    return tunnels[0]["display_address"], None
        except Exception as e:
            logger.error(f"Error fetching Playit address: {e}")
            return None, "❌ Unexpected error fetching Playit address."

async def setup(bot):
    await bot.add_cog(PlayitCog(bot))
