    
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
            
            # Gather information
            ip_address = getattr(config, 'SERVER_ADDRESS', 'slogikerserver.ddns.net')
            version = self._get_version()
            seed = self._get_seed()
            spawn = self._get_spawn()
            world_spawn = self._get_world_spawn()
            
            # Build plain text message with Discord markdown
            lines = [
                "━━━━━━━━━━━━━━━━━━━━━━━━",
                "🌍 **Server Information**",
                "━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"**Address:** `{ip_address}`",
                f"**Version:** `{version}`",
                f"**Seed:** `{seed}`",
            ]
            
            if spawn:
                lines.append(f"**Spawn:** `{spawn}`")
            
            if world_spawn:
                lines.append(f"**World Spawn:** `{world_spawn}`")
            
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            
            message_text = "\n".join(lines)
            
            # Check for existing bot message to edit
            message = None
            async for msg in channel.history(limit=5):
                if msg.author == self.bot.user:
                    message = msg
                    break
            
            if message:
                await message.edit(content=message_text)
            else:
                await channel.send(message_text)
                
            logger.info("Updated server info channel")
            
        except Exception as e:
            logger.error(f"Failed to update server info: {e}", exc_info=True)

    def _get_version(self) -> str:
        # Try to read installed version from config or properties
        try:
            from src.mc_manager import get_server_properties
            props = get_server_properties()
            if props:
                # MC doesn't store version in server.properties usually, 
                # but we might have it in our dynamic config
                pass
        except Exception:
            pass
        return config.get('installed_version', 'Unknown') 

    def _get_seed(self) -> str:
        # Read seed from server.properties
        try:
            from src.mc_manager import get_server_properties
            props = get_server_properties()
            if props:
                return props.get('level-seed', 'Random/Hidden')
        except Exception:
            pass
        return 'Random/Hidden'

    def _get_spawn(self) -> Optional[str]:
        # Read from config
        x = config.get(self.SPAWN_X_KEY)
        y = config.get(self.SPAWN_Y_KEY)
        z = config.get(self.SPAWN_Z_KEY)
        
        if x is not None and y is not None and z is not None:
             return f"X: {x}, Y: {y}, Z: {z}"
        return None
    
    def _get_world_spawn(self) -> Optional[str]:
        """Read world spawn from server.properties or level.dat"""
        try:
            from src.mc_manager import get_server_properties
            props = get_server_properties()
            if props:
                # Try to read spawn coordinates from properties
                spawn_x = props.get('spawn-x')
                spawn_y = props.get('spawn-y')
                spawn_z = props.get('spawn-z')
                
                if spawn_x is not None and spawn_y is not None and spawn_z is not None:
                    return f"X: {spawn_x}, Y: {spawn_y}, Z: {spawn_z}"
        except Exception as e:
            logger.debug(f"Could not read world spawn: {e}")
        
        return None

    async def set_spawn(self, x: int, y: int, z: int):
        # Update config file
        updates = {
            self.SPAWN_X_KEY: x,
            self.SPAWN_Y_KEY: y,
            self.SPAWN_Z_KEY: z
        }
        
        config.update_dynamic_config(updates)
        
        try:
            # Update config synchronously to avoid async race condition when threading
            c = config.load_bot_config()
            c.update(updates)
            config.save_bot_config(c)
            
            # Trigger update
            await self.update_info()
            return True
        except Exception as e:
            logger.error(f"Failed to save spawn info: {e}")
            return False

