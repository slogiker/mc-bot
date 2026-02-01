
import discord
import logging
import asyncio
from typing import Optional
from src.config import config
from src.logger import logger

class ServerInfoManager:
    """Manages the #server-information channel and its embed"""
    
    def __init__(self, bot):
        self.bot = bot
        self.channel_name = "server-information"
        # Config keys
        self.SPAWN_X_KEY = "spawn_x"
        self.SPAWN_Y_KEY = "spawn_y"
        self.SPAWN_Z_KEY = "spawn_z"
    
    async def get_or_create_channel(self, guild: discord.Guild) -> discord.TextChannel:
        """Get existing channel or create new one"""
        channel = discord.utils.get(guild.text_channels, name=self.channel_name)
        
        if not channel:
            # Create channel with specific permission overrides
            overrides = {
                guild.default_role: discord.PermissionOverwrite(send_messages=False, add_reactions=False),
                guild.me: discord.PermissionOverwrite(send_messages=True, embed_links=True)
            }
            channel = await guild.create_text_channel(
                name=self.channel_name,
                overwrites=overrides,
                reason="Server Information Channel"
            )
            logger.info(f"Created {self.channel_name} channel")
        
        return channel

    async def update_info(self, guild: discord.Guild = None):
        """Update the server information display"""
        if not guild:
            guild = self.bot.get_guild(int(config.GUILD_ID)) if config.GUILD_ID else None
        
        if not guild:
            logger.warning("Cannot update server info: Guild not found")
            return

        try:
            channel = await self.get_or_create_channel(guild)
            
            # Prepare Embed Data
            # IP: Fetch from config or hardcode as requested
            ip_address = "slogikerserver.ddns.net"
            
            # Version & Seed
            from src.mc_manager import mc_manager
            # Try to get real version/seed if server is running, otherwise use config/cache
            version = "Unknown"
            seed = "Unknown"
            
            # Try to get version from server.properties
            props = mc_manager.get_server_properties()
            if props:
                 # Seed isn't always in server.properties but we can check level.dat logic later
                 # For now, if user sets seed in setup it's in config, but better to read from properties if possible
                 pass
            
            # Since fetching version/seed via RCON requires server up, we rely on cached state or try RCON
            if self.bot.server.is_running():
                try:
                    # Async RCON calls to get data
                    pass
                except:
                    pass
            
            # Implementation detail: Use data we have. 
            # Version is usually set during setup.
            # Seed is in level.dat.
            
            # Let's start simple with a formatted embed and placeholders
            
            embed = discord.Embed(title="🌍 Server Information", color=0x5865F2)
            
            # We construct the description as requested
            desc_lines = [
                f"> **IP:** `{ip_address}`",
                f"> **Version:** `{self._get_version()}`",
                f"> **Seed:** `{self._get_seed()}`",
            ]
            
            # Add spawn if set
            spawn = self._get_spawn()
            if spawn:
                desc_lines.append(f"> **Spawn:** `{spawn}`")
                
            embed.description = "\n".join(desc_lines)
            
            # Check for existing bot message to edit
            message = None
            async for msg in channel.history(limit=5):
                if msg.author == self.bot.user:
                    message = msg
                    break
            
            if message:
                await message.edit(embed=embed)
            else:
                await channel.send(embed=embed)
                
            logger.info("Updated server info channel")
            
        except Exception as e:
            logger.error(f"Failed to update server info: {e}", exc_info=True)

    def _get_version(self) -> str:
        # Try to read installed version
        # This could be improved by storing version in a separate file during install
        # specific logic to find version jar or cache
        return config.get('installed_version', 'Unknown') 

    def _get_seed(self) -> str:
        # User requested to read seed from server.properties
        # It's actually in level.dat usually, but sometimes in server.properties if manually set
        from src.mc_manager import mc_manager
        props = mc_manager.get_server_properties()
        return props.get('level-seed', 'Random/Hidden')

    def _get_spawn(self) -> Optional[str]:
        # Read from config
        x = config.get(self.SPAWN_X_KEY)
        y = config.get(self.SPAWN_Y_KEY)
        z = config.get(self.SPAWN_Z_KEY)
        
        if x is not None and y is not None and z is not None:
             return f"X: {x}, Y: {y}, Z: {z}"
        return None

    async def set_spawn(self, x: int, y: int, z: int):
        # Update config file
        import json
        import aiofiles
        
        updates = {
            self.SPAWN_X_KEY: x,
            self.SPAWN_Y_KEY: y,
            self.SPAWN_Z_KEY: z
        }
        
        config.update_dynamic_config(updates)
        
        try:
            async with aiofiles.open('bot_config.json', 'r') as f:
                content = await f.read()
                data = json.loads(content)
            
            data.update(updates)
            
            async with aiofiles.open('bot_config.json', 'w') as f:
                await f.write(json.dumps(data, indent='\t') + '\n')
            
            # Trigger update
            await self.update_info()
            return True
        except Exception as e:
            logger.error(f"Failed to save spawn info: {e}")
            return False

