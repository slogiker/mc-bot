import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import os
from src.logger import logger
from src.utils import has_role

class PlayitCog(commands.Cog):
    """
    Manages Playit.gg integration details.
    Allows retrieving the public connection address via Playit API.
    """
    def __init__(self, bot):
        self.bot = bot
        self.cached_address = None
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

    @app_commands.command(name="ip", description="Get the public Playit.gg address")
    async def get_ip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        # 1. Check cache first
        if self.cached_address:
            await interaction.followup.send(f"🌍 **Public Address**: `{self.cached_address}`")
            return

        # 2. Fetch from Playit API
        address = await self.fetch_playit_address()
        
        if address:
            self.cached_address = address
            self.tunnels = [address]
            await interaction.followup.send(f"🌍 **Public Address**: `{address}`")
        else:
            await interaction.followup.send("❌ Could not determine Playit address. Is the tunnel running or is the Secret Key missing?")

    async def fetch_playit_address(self):
        """
        Fetches the tunnel address via Playit REST API.
        """
        secret_key = self.get_secret_key()
        if not secret_key:
            logger.warning("No Playit secret key found. Cannot fetch IP.")
            return None

        url = "https://api.playit.gg/account/tunnels"
        headers = {
            "Authorization": f"agent-key {secret_key}"
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Playit API returned status {resp.status}: {await resp.text()}")
                        return None
                    
                    data = await resp.json()
                    
                    # Search for a minecraft-java tunnel
                    for tunnel in data:
                        if tunnel.get("tunnel_type") == "minecraft-java" and tunnel.get("custom_domain"):
                            return tunnel.get("custom_domain")

                    # Fallback to the first tunnel's formatted address if no explicit java one found
                    for tunnel in data:
                        if tunnel.get("custom_domain"):
                            return tunnel.get("custom_domain")
                        if tunnel.get("alloc"):
                            alloc = tunnel.get("alloc")
                            return f"{alloc.get('connect_address_v4', '')}:{alloc.get('connect_port_v4', '')}".strip(":")

            return None
        except Exception as e:
            logger.error(f"Error fetching Playit address from API: {e}")
            return None

async def setup(bot):
    await bot.add_cog(PlayitCog(bot))
