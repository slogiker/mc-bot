import os
import json
import asyncio
from aiomcrcon import Client

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
