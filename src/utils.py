import os
import json
import asyncio
import discord
from discord import app_commands
from aiomcrcon import Client
from src.config import config
from src.logger import logger

async def send_debug(bot, msg: str):
    """Send a debug message to the debug channel and log it."""
    logger.info(f"[DEBUG] {msg}")
    ch = bot.get_channel(config.DEBUG_CHANNEL_ID)
    if ch:
        try:
            await ch.send(f"[DEBUG] {msg}")
        except Exception as e:
            logger.error(f"Failed to send debug message: {e}")

def has_role(cmd_name):
    """Check if the user has the required role for a command."""
    async def predicate(interaction):
        # Use config.ROLE_PERMISSIONS (Name -> [cmds])
        # TODO: Switch to using config.ROLES (ID -> [cmds]) for robust checks against role renames
        role_permissions = config.ROLE_PERMISSIONS
        
        # Check user's roles by NAME
        for role in interaction.user.roles:
            if cmd_name in role_permissions.get(role.name, []):
                return True
        
        # Check @everyone
        if cmd_name in role_permissions.get("@everyone", []):
            return True

        await send_debug(interaction.client, f"Check failed: {interaction.user.mention} lacks role for command '{cmd_name}'.")
        
        # Helper to list allowed roles
        allowed_roles = [r for r, cmds in role_permissions.items() if cmd_name in cmds]
        await interaction.response.send_message(f"❌ You need one of these roles: {', '.join(allowed_roles)}", ephemeral=True)
        return False
    return app_commands.check(predicate)

async def rcon_cmd(cmd):
    """Execute an RCON command on the Minecraft server asynchronously."""
    try:
        async with Client(config.RCON_HOST, config.RCON_PORT, config.RCON_PASSWORD) as client:
            return await client.send_cmd(cmd)
    except Exception as e:
        error_msg = f"RCON failed ({cmd}): {e}"
        logger.error(error_msg)
        return "❌ Server is not running or RCON is unavailable"

async def get_uuid(username):
    """Retrieve a player's UUID from usercache.json."""
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

def map_key(key):
    """Map user input to Minecraft stat key format."""
    return f"minecraft:{key.lower()}"

def display_key(key):
    """Remove 'minecraft:' prefix for display."""
    if key.startswith("minecraft:"):
        return key[10:]
    return key

async def parse_server_version():
    """Parse Minecraft version from latest.log asynchronously."""
    import aiofiles
    # TODO: Update to use Docker logs introspection or configured version
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
