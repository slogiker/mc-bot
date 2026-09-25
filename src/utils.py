import os
import json
import asyncio
from datetime import datetime
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

def check_user_permission(user: discord.Member, cmd_name: str, guild: discord.Guild) -> bool:
    """
    Check if a user has permission to run a command/action.
    
    Checks in order:
    1. Bot Owner (using config.OWNER_ID)
    2. Guild Owner
    3. Discord Administrator permission
    4. Role ID match in `config.ROLES`
    5. Role Name match in `config.ROLE_PERMISSIONS` (Legacy/Fallback)
    6. `@everyone` role ID or name match
    
    Args:
        user (discord.Member): The member to check.
        cmd_name (str): The permission/command name.
        guild (discord.Guild): The guild where the command is executed.
        
    Returns:
        bool: True if the user has permission, False otherwise.
    """
    # 1. Bot Owner
    if user.id == config.OWNER_ID:
        return True

    # 2. Guild Owner
    if guild and user.id == guild.owner_id:
        return True

    # 3. Discord Administrator permission
    if isinstance(user, discord.Member) and user.guild_permissions.administrator:
        return True

    # 4. Check Permissions by Role ID (Preferred)
    user_roles = getattr(user, 'roles', [])
    for role in user_roles:
        if cmd_name in config.ROLES.get(str(role.id), []):
            return True

    # 5. Check Permissions by Role Name (Legacy/Fallback)
    permissions = config.ROLE_PERMISSIONS
    for role in user_roles:
        if cmd_name in permissions.get(role.name, []):
            return True

    # 6. Check @everyone (ID and Name)
    if guild:
        if cmd_name in config.ROLES.get(str(guild.default_role.id), []):
            return True
    if cmd_name in permissions.get("@everyone", []):
        return True

    return False

def has_role(cmd_name: str):
    """
    Decorator to check if the user has the required role for a command.
    
    It delegates to `check_user_permission` for verification.
    
    Args:
        cmd_name (str): The internal name of the command permission to check.
    """
    async def predicate(interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return False
            
        if check_user_permission(interaction.user, cmd_name, interaction.guild):
            return True

        await send_debug(interaction.client, f"Check failed: {interaction.user.mention} ({interaction.user.id}) lacks role for '{cmd_name}'.")
        
        allowed_roles = [r for r, cmds in config.ROLE_PERMISSIONS.items() if cmd_name in cmds]
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

async def get_server_version() -> str:
    """
    Get the Minecraft server version using a single source of truth.
    Checks config, versions directory, and logs, auto-persisting detected version to config.
    """
    # 1. Config installed_version
    installed_ver = getattr(config, 'INSTALLED_VERSION', None)
    if isinstance(installed_ver, str) and installed_ver.strip() not in ("", "None", "Unknown", "unknown"):
        return installed_ver.strip()

    detected_ver = None

    # 2. Check mc-server/versions/ directory
    try:
        versions_dir = os.path.join(config.SERVER_DIR, "versions")
        if os.path.isdir(versions_dir):
            subdirs = [
                d for d in os.listdir(versions_dir)
                if os.path.isdir(os.path.join(versions_dir, d)) and not d.startswith(".")
            ]
            if subdirs:
                # Pick the latest version directory
                subdirs.sort(reverse=True)
                detected_ver = subdirs[0]
    except Exception as e:
        logger.debug(f"Error checking versions dir: {e}")

    # 3. Check logs/latest.log
    if not detected_ver:
        log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
        if os.path.exists(log_path):
            try:
                import aiofiles
                import re
                async with aiofiles.open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    async for line in f:
                        if "Starting minecraft server version" in line:
                            match = re.search(r'Starting minecraft server version\s+([0-9a-zA-Z._\-]+)', line)
                            if match:
                                detected_ver = match.group(1)
                                break
                        elif "Loading Minecraft" in line and "Fabric Loader" in line:
                            match = re.search(r'Loading Minecraft\s+([0-9a-zA-Z._\-]+)', line)
                            if match:
                                detected_ver = match.group(1)
                                break
            except Exception as e:
                logger.debug(f"Failed to scan latest.log for version: {e}")

    if detected_ver:
        # Self-repair: persist detected version to bot_config.json
        try:
            with config.update_bot_config() as bot_cfg:
                bot_cfg['installed_version'] = detected_ver
            config.INSTALLED_VERSION = detected_ver
            logger.info(f"Self-repair: Auto-detected and saved installed_version: {detected_ver}")
        except Exception as e:
            logger.warning(f"Could not persist detected version to config: {e}")
        return detected_ver

    return "Unknown"


async def get_server_platform() -> str:
    """
    Get the Minecraft server platform (fabric, paper, etc.) and auto-persist to config.
    """
    installed_plat = getattr(config, 'INSTALLED_PLATFORM', None)
    if isinstance(installed_plat, str) and installed_plat.strip() not in ("", "None", "Unknown", "unknown"):
        return installed_plat.strip().lower()

    detected_plat = None
    server_dir = config.SERVER_DIR

    # Detect Fabric
    if os.path.exists(os.path.join(server_dir, ".fabric")) or \
       os.path.exists(os.path.join(server_dir, "fabric-server-launch.jar")) or \
       os.path.exists(os.path.join(server_dir, "libraries", "net", "fabricmc")):
        detected_plat = "fabric"
    # Detect Paper / Purpur / Spigot
    elif os.path.exists(os.path.join(server_dir, "paper.yml")) or \
         os.path.exists(os.path.join(server_dir, "config", "paper-global.yml")):
        detected_plat = "paper"
    elif os.path.exists(os.path.join(server_dir, "purpur.yml")):
        detected_plat = "purpur"
    elif os.path.exists(os.path.join(server_dir, "spigot.yml")):
        detected_plat = "spigot"
    elif os.path.exists(os.path.join(server_dir, "server.jar")):
        detected_plat = "vanilla"

    if detected_plat:
        try:
            with config.update_bot_config() as bot_cfg:
                bot_cfg['installed_platform'] = detected_plat
            config.INSTALLED_PLATFORM = detected_plat
            logger.info(f"Self-repair: Auto-detected and saved installed_platform: {detected_plat}")
        except Exception as e:
            logger.warning(f"Could not persist detected platform to config: {e}")
        return detected_plat

    return "paper"


async def get_server_seed(bot=None) -> str:
    """
    Get the world seed using persisted cache, RCON, or level.dat, and auto-persist.
    """
    stored_seed = config.get('cached_seed')
    if stored_seed:
        return str(stored_seed)

    detected_seed = None

    # Try RCON if server running
    if bot and hasattr(bot, 'server') and bot.server.is_running():
        try:
            from src.utils import rcon_cmd
            import re
            success, response = await rcon_cmd("seed")
            if success and response:
                match = re.search(r'Seed: \[(-?\d+)\]', response)
                if match:
                    detected_seed = match.group(1)
        except Exception as e:
            logger.debug(f"RCON seed query failed: {e}")

    # Try parsing level.dat
    if not detected_seed:
        try:
            import nbtlib
            level_dat = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER, "level.dat")
            if os.path.exists(level_dat):
                data = await asyncio.to_thread(nbtlib.load, level_dat)
                try:
                    detected_seed = str(int(data["Data"]["WorldGenSettings"]["dimensions"]["minecraft:overworld"]["generator"]["seed"]))
                except (KeyError, TypeError):
                    try:
                        detected_seed = str(int(data["Data"]["WorldGenSettings"]["seed"]))
                    except (KeyError, TypeError):
                        try:
                            detected_seed = str(int(data["Data"]["RandomSeed"]))
                        except (KeyError, TypeError):
                            pass
        except Exception as e:
            logger.debug(f"level.dat seed parse failed: {e}")

    if detected_seed:
        try:
            with config.update_bot_config() as config_data:
                config_data['cached_seed'] = detected_seed
            logger.info(f"Self-repair: Auto-detected and saved cached_seed: {detected_seed}")
        except Exception as e:
            logger.warning(f"Could not persist seed to config: {e}")
        return detected_seed

    return "Unknown"


def quarantine_incompatible_mod(mod_identifier: str) -> str | None:
    """
    Quarantine an incompatible mod jar to mc-server/mods/quarantined/.
    Returns the quarantined filename if found and moved, else None.
    """
    import shutil
    mods_dir = os.path.join(config.SERVER_DIR, "mods")
    if not os.path.isdir(mods_dir):
        return None

    quarantine_dir = os.path.join(mods_dir, "quarantined")
    os.makedirs(quarantine_dir, exist_ok=True)

    clean_id = mod_identifier.lower().replace("-", "").replace("_", "")
    target_file = None
    for fname in os.listdir(mods_dir):
        if not fname.endswith(".jar"):
            continue
        clean_name = fname.lower().replace("-", "").replace("_", "")
        if clean_id in clean_name or mod_identifier.lower() in fname.lower():
            target_file = fname
            break

    if target_file:
        src = os.path.join(mods_dir, target_file)
        dst = os.path.join(quarantine_dir, target_file)
        try:
            shutil.move(src, dst)
            logger.warning(f"Quarantined incompatible mod: {target_file} -> {dst}")
            return target_file
        except Exception as e:
            logger.error(f"Failed to quarantine mod {target_file}: {e}")

    return None


async def parse_server_version():
    """Parse Minecraft version asynchronously with auto-detection and persistence."""
    return await get_server_version()


def get_timezone():
    """Returns the configured pytz timezone object."""
    import pytz
    tz_name = getattr(config, 'TIMEZONE', 'UTC')
    try:
        return pytz.timezone(tz_name)
    except Exception:
        return pytz.UTC


def get_now() -> datetime:
    """Returns the current datetime in the configured timezone."""
    from datetime import datetime
    return datetime.now(get_timezone())

