import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import os
import time
from src.logger import logger
from src.utils import has_role

# Cache expires after 2 hours (7200 seconds)
CACHE_TTL = 7200

class PlayitCog(commands.Cog):
    """
    Manages Playit.gg integration details.
    Allows retrieving the public connection address via Playit API.
    """
    def __init__(self, bot):
        self.bot = bot
        self.cached_address = None
        self.cache_time = None
        self.tunnels = []

    def get_secret_key(self):
        """Get Playit secret key from data file or env."""
        key_path = "/app/data/playit_secret.key"
        try:
            if os.path.exists(key_path):
                with open(key_path, "r") as f:
                    return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read playit secret key from {key_path}: {e}")
        
        # Fallback to env
        return os.environ.get("PLAYIT_SECRET_KEY", "").strip()

    def _is_cache_valid(self):
        """Check if cached address is still valid (within TTL)."""
        if self.cached_address and self.cache_time:
            return (time.time() - self.cache_time) < CACHE_TTL
        return False

    @app_commands.command(name="ip", description="Get the public Playit.gg address")
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
            logger.warning("No Playit secret key found. Cannot fetch IP.")
            return None, "❌ No Playit secret key found. Run the installer or add your key to `data/playit_secret.key`."

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
                        logger.error("Playit API returned 401 Unauthorized")
                        return None, "❌ Playit rejected the secret key (401 Unauthorized). Your key may be expired or invalid."
                    elif resp.status != 200:
                        logger.error(f"Playit API returned status {resp.status}: {await resp.text()}")
                        return None, f"❌ Playit API returned error (status {resp.status}). Is your tunnel claimed?"

                    data = await resp.json()
                    logger.debug(f"Playit API raw response: {data}")

                    tunnels = data.get("data", {}).get("tunnels", [])
                    if not tunnels:
                        return None, "❌ No tunnels configured on your Playit account. Create one at https://playit.gg"

                    # Prefer minecraft-java tunnel, fallback to first
                    for tunnel in tunnels:
                        if tunnel.get("tunnel_type") == "minecraft-java":
                            return tunnel["display_address"], None
                    return tunnels[0]["display_address"], None

            return None, "❌ Tunnels exist but none have an address assigned yet. The tunnel may still be initializing."
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Playit address: {e}")
            return None, "❌ Could not reach the Playit API. Check your internet connection."
        except Exception as e:
            logger.error(f"Error fetching Playit address from API: {e}")
            return None, "❌ Unexpected error fetching Playit address. Check bot logs for details."

async def setup(bot):
    await bot.add_cog(PlayitCog(bot))
