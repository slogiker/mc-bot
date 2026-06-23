import os
import json
import asyncio
import discord
from discord import app_commands
from src.config import config
from src.logger import logger

async def send_debug(bot: discord.Client, msg: str) -> None:
    """
    Send a debug message to the configured debug channel and log it.
    
    Args:
        bot (discord.Client): The bot instance.
        msg (str): The debug message to send.
    """
    logger.info(f"[DEBUG] {msg}")
    ch = bot.get_channel(config.DEBUG_CHANNEL_ID)
    if ch:
        try:
            await ch.send(f"[DEBUG] {msg}")
        except Exception as e:
            logger.error(f"Failed to send debug message: {e}")

def has_role(cmd_name: str):
    """
    Decorator to check if the user has the required role for a command.
    
    It performs a 3-step check:
    1. Check if user has a role ID that is mapped to the command in `config.ROLES`.
    2. Check if user has a role NAME that is mapped to the command in `user_config` (Legacy/Fallback).
    3. Check if @everyone has permission (ID or Name).
    
    Args:
        cmd_name (str): The internal name of the command permission to check.
    """
    async def predicate(interaction):
        # 0. Guild Owner ALWAYS has full access to all commands
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        # 1. Check Permissions by Role ID (Preferred)
        # config.ROLES is populated with Role ID -> [commands] in resolve_role_permissions
        for role in interaction.user.roles:
            if cmd_name in config.ROLES.get(str(role.id), []):
                return True
                
        # 2. Check Permissions by Role Name (Legacy/Fallback)
        # Use in-memory config.ROLE_PERMISSIONS instead of reading from disk
        permissions = config.ROLE_PERMISSIONS
        
        for role in interaction.user.roles:
            if cmd_name in permissions.get(role.name, []):
                return True

        # 3. Check @everyone (ID and Name)
        if cmd_name in config.ROLES.get(str(interaction.guild.default_role.id), []):
            return True
        if cmd_name in permissions.get("@everyone", []):
            return True

        await send_debug(interaction.client, f"Check failed: {interaction.user.mention} ({interaction.user.id}) lacks role for '{cmd_name}'.")
        
        allowed_roles = [r for r, cmds in permissions.items() if cmd_name in cmds]
        await interaction.response.send_message(f"❌ You need one of these roles: {', '.join(allowed_roles)}", ephemeral=True)
        return False

    # Store the required permission name for help command inspection
    predicate._required_permission = cmd_name
    return app_commands.check(predicate)

async def rcon_cmd(cmd: str) -> tuple[bool, str]:
    """
    Execute an RCON command on the Minecraft server asynchronously.
    Uses rcon_manager for persistent, efficient connections.
    """
    from src.rcon_manager import rcon_manager
    return await rcon_manager.send_command(cmd)

async def get_uuid(username: str) -> str | None:
    """
    Retrieve a player's UUID from the server's `usercache.json`.
    
    Args:
        username (str): The Minecraft username.
        
    Returns:
        str | None: The UUID string including hyphens, or None if not found.
    """
    import aiofiles
    usercache_path = os.path.join(config.SERVER_DIR, 'usercache.json')
    
    try:
        # Use asyncio.to_thread for os.path.exists check
        exists = await asyncio.to_thread(os.path.exists, usercache_path)
        if not exists:
            return None
        
        # Use aiofiles for reading
        try:
            async with aiofiles.open(usercache_path, 'r') as f:
                content = await f.read()
                users = json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to read usercache.json: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading usercache.json: {e}")
            return None
        
        # Validate users is a list
        if not isinstance(users, list):
            logger.error("usercache.json does not contain a list")
            return None
        
        for user in users:
            if isinstance(user, dict) and user.get('name', '').lower() == username.lower():
                return user.get('uuid')
        return None
    except Exception as e:
        logger.error(f"Error in get_uuid: {e}")
        return None

async def get_server_mod_folder() -> str | None:
    """
    Detect whether to use 'mods' or 'plugins' folder based on server structure and platform.
    Returns 'plugins', 'mods', or None (for Vanilla).
    """
    platform = getattr(config, 'INSTALLED_PLATFORM', None)
    if platform == 'vanilla':
        return None
        
    plugins_path = os.path.join(config.SERVER_DIR, "plugins")
    if await asyncio.to_thread(os.path.exists, plugins_path):
        return "plugins"
        
    mods_path = os.path.join(config.SERVER_DIR, "mods")
    if await asyncio.to_thread(os.path.exists, mods_path):
        return "mods"
        
    # Guess based on platform if folders don't exist yet (e.g. during first setup)
    if platform == 'paper':
        return 'plugins'
    elif platform == 'fabric':
        return 'mods'
        
    return None

async def get_dir_size_gb(start_path='.') -> float:
    """
    Calculate the total size of a directory in GB asynchronously.
    """
    def get_size():
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(start_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    # skip if it is symbolic link
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        except Exception as e:
            logger.debug(f"Error calculating dir size: {e}")
        return total_size / (1024**3)
        
    return await asyncio.to_thread(get_size)

async def parse_server_version():
    """Parse Minecraft version from latest.log asynchronously."""
    import aiofiles
    # Reading the file directly is acceptable here as we need to scan the start of the log
    # which docker logs might not return if the container has been running for a long time.
    log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
    
    exists = await asyncio.to_thread(os.path.exists, log_path)
    if not exists:
        return "Unknown"
    
    try:
        async with aiofiles.open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            async for line in f:
                if "Starting minecraft server version" in line:
                    parts = line.split()
                    for part in parts:
                        if part.startswith('1.') or part.startswith('2.'):
                            return part
    except Exception as e:
        logger.error(f"Failed to parse server version: {e}")
    
    return "Unknown"
