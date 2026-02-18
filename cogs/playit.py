import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re
from src.logger import logger
from src.utils import has_role

class PlayitCog(commands.Cog):
    """
    Manages Playit.gg integration details.
    Allows retrieving the public connection address.
    """
    def __init__(self, bot):
        self.bot = bot
        self.cached_address = None

    @app_commands.command(name="ip", description="Get the public Playit.gg address")
    async def get_ip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        # 1. Check cache first
        if self.cached_address:
            await interaction.followup.send(f"🌍 **Public Address**: `{self.cached_address}`")
            return

        # 2. Fetch from Docker logs
        address = await self.fetch_playit_address()
        
        if address:
            self.cached_address = address
            await interaction.followup.send(f"🌍 **Public Address**: `{address}`")
        else:
            await interaction.followup.send("❌ Could not determine Playit address. Is the tunnel running?")

    async def fetch_playit_address(self):
        """
        Scans `docker logs mc-bot-playit` for the assigned address.
        """
        container_name = "mc-bot-playit"
        try:
            # Get last 100 lines of logs
            process = await asyncio.create_subprocess_exec(
                'docker', 'logs', '--tail', '100', container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Failed to read playit logs: {stderr.decode()}")
                return None
                
            logs = stdout.decode('utf-8', errors='ignore')
            
            # Parsing logic
            # Playit logs usually look like:
            # "tunnel running check connection: tcp://<domain>:<port>" or similar
            # Or just search for the specific playit domain pattern
            
            # Generic match for commonly used domains in free tier, but user might have custom.
            # Best bet: look for "https://playit.gg/t/<id>" and then maybe lines after?
            # Or look for "address": "..." in JSON if it logs JSON.
            # Typical log: "INFO tunnel defined: ... => ... (minecraft-java) @ <address>"
            
            # Simple heuristic: Look for lines containing "tunnel defined" or "tunnel running"
            # and extract the domain part.
            
            # Let's look for valid domain patterns that are NOT playit.gg website URLs
            # Regex: ([\w-]+\.[\w-]+\.[a-z]+(?::\d+)?)
            
            # Better specific heuristic based on known output:
            lines = logs.split('\n')
            for line in reversed(lines):
                # Search for typical allocation line
                # "starting tunnel ... => ... @ <ADDRESS>"
                if "@" in line and "=>" in line:
                    parts = line.split("@")
                    if len(parts) > 1:
                        addr = parts[-1].strip()
                        # Verify it looks like an address
                        if "." in addr:
                            return addr
                            
            return None

        except Exception as e:
            logger.error(f"Error fetching Playit address: {e}")
            return None

async def setup(bot):
    await bot.add_cog(PlayitCog(bot))
