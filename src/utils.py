import os
import json
import asyncio
import discord
from discord import app_commands
from aiomcrcon import Client
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
        # Use config.ROLES which maps Role ID -> [commands]
        # This is populated by config.resolve_role_permissions(guild)
        
        # 1. Check Permissions by Role ID (Preferred)
        for role in interaction.user.roles:
            if cmd_name in config.ROLES.get(str(role.id), []):
                return True
                
        # 2. Check Permissions by Role Name (Legacy/Fallback)
        # This handles cases where ID mapping might be missing or config uses names directly
        # and resolve_role_permissions hasn't run or missed something.
        # Although resolve_role_permissions maps names to IDs, we double check config.ROLE_PERMISSIONS
        # just in case `interaction.user.roles` has a name that matches directly.
        
        user_config = config.load_user_config()
        permissions = user_config.get('permissions', {})
        
        for role in interaction.user.roles:
            if cmd_name in permissions.get(role.name, []):
                return True

        # 3. Check @everyone (ID and Name)
        if cmd_name in config.ROLES.get(str(interaction.guild.default_role.id), []):
            return True
        if cmd_name in permissions.get("@everyone", []):
            return True

        await send_debug(interaction.client, f"Check failed: {interaction.user.mention} ({interaction.user.id}) lacks role for '{cmd_name}'.")
        
        # Helper to list allowed roles (friendly names)
        # We can reconstruct this from permissions dict
        allowed_roles = [r for r, cmds in permissions.items() if cmd_name in cmds]
        await interaction.response.send_message(f"❌ You need one of these roles: {', '.join(allowed_roles)}", ephemeral=True)
        return False
    return app_commands.check(predicate)

async def rcon_cmd(cmd: str) -> str:
    """
    Execute an RCON command on the Minecraft server asynchronously.
    
    Args:
        cmd (str): The command to execute (e.g., "list", "say hello").
        
    Returns:
        str: The response from the server, or an error message if failed.
    """
    try:
        async with Client(config.RCON_HOST, config.RCON_PORT, config.RCON_PASSWORD) as client:
            return await client.send_cmd(cmd)
    except Exception as e:
        error_msg = f"RCON failed ({cmd}): {e}"
        logger.error(error_msg)
        return "❌ Server is not running or RCON is unavailable"

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
