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
        user_role_ids = [str(role.id) for role in interaction.user.roles]
        # Check against config.ROLES
        # config.ROLES is dict: {role_id: [cmd1, cmd2]}
        for role_id in user_role_ids:
            if cmd_name in config.ROLES.get(role_id, []):
                return True
        
        await send_debug(interaction.client, f"Check failed: {interaction.user.mention} lacks role for command '{cmd_name}'.")
        await interaction.response.send_message("❌ Prosim, dobi ustrezno vlogo.", ephemeral=True)
        return False
    return app_commands.check(predicate)

async def rcon_cmd(cmd):
    """Execute an RCON command on the Minecraft server asynchronously."""
    if config.TEST_MODE:
        logger.info(f"[MOCK RCON] Executing: {cmd}")
        if cmd == "list":
            return "There are 0 of a max of 20 players online: "
        return "Executed command (MOCK)"

    try:
        async with Client(config.RCON_HOST, config.RCON_PORT, config.RCON_PASSWORD) as client:
            return await client.send_cmd(cmd)
    except Exception as e:
        error_msg = f"RCON failed ({cmd}): {e}"
        logger.error(error_msg)
        return "❌ Server is not running or RCON is unavailable"

def get_uuid(username):
    """Retrieve a player's UUID from usercache.json."""
    usercache_path = os.path.join(config.SERVER_DIR, 'usercache.json')
    if not os.path.exists(usercache_path):
        return None
    with open(usercache_path, 'r') as f:
        users = json.load(f)
    for user in users:
        if user['name'].lower() == username.lower():
            return user['uuid']
    return None

def map_key(key):
    """Map user input to Minecraft stat key format."""
    return f"minecraft:{key.lower()}"

def display_key(key):
    """Remove 'minecraft:' prefix for display."""
    if key.startswith("minecraft:"):
        return key[10:]
    return key
