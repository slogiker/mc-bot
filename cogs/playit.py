import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import os
import re
import time
import psutil
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

    def get_secret_key(self):
        """Get Playit secret key from data file."""
        key_path = os.path.join("data", "playit_secret.key")
        if os.path.exists(key_path):
            try:
                with open(key_path, "r") as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Failed to read playit secret key: {e}")
        
        # Fallback to env
        return os.environ.get("PLAYIT_SECRET_KEY", "").strip()

    async def start_tunnel(self):
        """Starts or restarts the playit tunnel and watches for a claim link."""
        logger.info("Playit: Starting tunnel...")
        secret_key_path = os.path.join("data", "playit_secret.key")
        socket_path = os.path.join("data", "playit.sock")
        log_path = os.path.join("logs", "playit.log")

        # Kill existing if any
        await asyncio.create_subprocess_shell("tmux kill-session -t playit", stderr=asyncio.subprocess.DEVNULL)
        
        # Build command
        cmd = ["playit", "--platform-docker", "--socket-path", socket_path, "-l", log_path]
        if os.path.exists(secret_key_path) and os.path.getsize(secret_key_path) > 0:
            cmd.extend(["--secret-path", secret_key_path])

        # Start in tmux
        start_cmd = f"tmux new-session -d -s playit '{' '.join(cmd)}'"
        proc = await asyncio.create_subprocess_shell(start_cmd)
        await proc.wait()

        # Watch log for claim link
        await asyncio.sleep(2)
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    content = f.read()
                    # Look for https://playit.gg/claim/XXXX-XXXX
                    match = re.search(r'https://playit\.gg/claim/[A-Z0-9-]+', content)
                    if match:
                        self._claim_link = match.group(0)
                        logger.info(f"Playit: Found claim link: {self._claim_link}")
                    else:
                        self._claim_link = None
            except Exception as e:
                logger.error(f"Error reading playit log: {e}")

    def _is_cache_valid(self):
        """Check if cached address is still valid (within TTL)."""
        if self.cached_address and self.cache_time:
            return (time.time() - self.cache_time) < CACHE_TTL
        return False

    @app_commands.command(name="status", description="Show detailed bot and server status")
    @has_role("status")
    async def status_combined(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Build status embed
        embed = discord.Embed(title="🖥️ Server Status", color=discord.Color.blue())
        
        # 1. Minecraft Status
        mc_status = "🟢 Online" if self.bot.server.is_running() else "🔴 Offline"
        if self.bot.server.is_intentionally_stopped():
            mc_status = "⚪ Stopped"
        embed.add_field(name="Minecraft", value=mc_status, inline=True)

        # 2. Playit Status
        address, error = await self.fetch_playit_address()
        if address:
            playit_status = f"🟢 Connected\n`{address}`"
        elif self._claim_link:
            playit_status = "🟡 Unclaimed\nUse `/playit claim`"
        else:
            playit_status = f"🔴 Error\n{error or 'Not running'}"
        embed.add_field(name="Tunnel (Playit)", value=playit_status, inline=True)

        # 3. Hardware
        usage = psutil.disk_usage('/')
        embed.add_field(name="Disk Space", value=f"{usage.percent}% used", inline=True)
        
        await interaction.followup.send(embed=embed)

    playit_group = app_commands.Group(name="playit", description="Playit.gg tunnel management")

    @playit_group.command(name="claim", description="Get the claim link for a new tunnel")
    @has_role("admin")
    async def playit_claim(self, interaction: discord.Interaction):
        if self._claim_link:
            await interaction.response.send_message(
                f"🔗 **Playit Claim Link**: {self._claim_link}\n\n"
                "Click the link to assign this bot to your Playit.gg account. "
                "Once claimed, run `/playit restart` to finish setup.",
                ephemeral=True
            )
        else:
            # Try to restart and find it
            await interaction.response.defer(ephemeral=True)
            await self.start_tunnel()
            if self._claim_link:
                await interaction.followup.send(f"🔗 **Claim Link Generated**: {self._claim_link}")
            else:
                await interaction.followup.send("❌ Could not generate a claim link. Check bot logs.")

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
        
        # 1. Check cache (with TTL)
        if self._is_cache_valid():
            await interaction.followup.send(f"🌍 **Public Address**: `{self.cached_address}`")
            return

        # 2. Fetch from Playit API
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
        
        Returns:
            tuple: (address, error_message) — one will be None
        """
        secret_key = self.get_secret_key()
        if not secret_key:
            return None, "❌ No Playit secret key found."

        url = "https://api.playit.gg/v1/agents/rundata"
        headers = {
            "Authorization": f"Agent-Key {secret_key}",
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json={}) as resp:
                    if resp.status == 401:
                        return None, "❌ Playit rejected the secret key (401 Unauthorized)."
                    elif resp.status != 200:
                        return None, f"❌ Playit API returned error (status {resp.status})."

                    data = await resp.json()
                    tunnels = data.get("data", {}).get("tunnels", [])
                    if not tunnels:
                        return None, "❌ No tunnels configured on your Playit account."

                    # Prefer minecraft-java tunnel
                    for tunnel in tunnels:
                        if tunnel.get("tunnel_type") == "minecraft-java":
                            return tunnel["display_address"], None
                    return tunnels[0]["display_address"], None

        except Exception as e:
            logger.error(f"Error fetching Playit address: {e}")
            return None, "❌ Unexpected error fetching Playit address."

async def setup(bot):
    await bot.add_cog(PlayitCog(bot))
