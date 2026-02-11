#            Made by slogiker - All rights reserved v6
#
import discord
from discord import Activity, ActivityType, Status, app_commands
from discord.ext import commands, tasks
import asyncio
import subprocess
import os
import psutil
import logging
import json
from datetime import datetime, time as dt_time
import re
import aiofiles
import hashlib
import uuid
import requests
import shutil
import zipfile
from collections import deque
import atexit
import time
import sys
from logging.handlers import RotatingFileHandler
from mcrcon import MCRcon
from dotenv import load_dotenv


# --- Custom Formatter for [HH:MM:SS - DD.MM.YYYY] ---
class CustomFormatter(logging.Formatter):
    def format(self, record):
        timestamp = datetime.now().strftime('%H:%M:%S - %d.%m.%Y')
        return f"[{timestamp}] {record.levelname:<8} {record.msg}"

# --- Redirect Terminal Output to Logger ---
class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, buf):
        if buf.strip():
            for line in buf.rstrip().splitlines():
                self.logger.log(self.level, f"[TERMINAL] {line.rstrip()}")

    def flush(self):
        pass

# --- Logging Setup ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = []  # Clear any existing handlers

formatter = CustomFormatter()
file_handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=5)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

# Redirect stderr to logger
sys.stderr = StreamToLogger(logger, logging.ERROR)

# --- Env configuration ---

load_dotenv()

TOKEN                = os.getenv("BOT_TOKEN")
RCON_PASSWORD        = os.getenv("RCON_PASSWORD")

# --- Load Configuration ---
with open('config.json', 'r') as f:
    config = json.load(f)


RCON_HOST            = config['rcon_host']
RCON_PORT            = config['rcon_port']
COMMAND_CHANNEL_ID   = config['command_channel_id']
LOG_CHANNEL_ID       = config['log_channel_id']
DEBUG_CHANNEL_ID     = config['debug_channel_id']
ADMIN_ROLE_ID        = config['owner_role_id']
SERVER_DIR           = config['server_directory']
SERVER_JAR           = config['server_jar']
WORLD_FOLDER         = config.get('world_folder', 'world')
JAVA_XMS             = config['java_xms']
JAVA_XMX             = config['java_xmx']
BACKUP_TIME          = config['backup_time']            # "HH:MM"
BACKUP_RETENTION_DAYS= config['backup_retention_days']
RESTART_TIME         = config['restart_time']           # "HH:MM"
RESTART_DELAY        = config['restart_delay_s']
CRASH_CHECK_INTERVAL = config['crash_check_interval_s']
LOG_LINES_DEFAULT    = config['log_lines_default']
STATUS_COOLDOWN      = config['status_cooldown_s']
LOGS_COOLDOWN        = config['logs_cooldown_s']
GUILD_ID             = config['guild_id']
STATE_FILE           = config['intentional_stop']

# --- State File Functions ---
def load_server_state():
    state_file = STATE_FILE
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)
            return state.get('intentional_stop', True)  # Default to True
    return True

def save_server_state():
    state_file = 'server_state.json'
    with open(state_file, 'w') as f:
        json.dump({'intentional_stop': intentional_stop}, f)

# --- Global State ---
server_start_time = None
intentional_stop  = load_server_state()
restart_lock      = asyncio.Lock()
last_used         = {}  # {(user_id, cmd): datetime}
restart_attempts  = 0
MAX_RESTART_ATTEMPTS = 3
restart_failed    = False
server_process    = None
server_online = False

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# --- Helper Functions ---
async def update_bot_presence():
    """Update bot's Discord presence based on global server state."""
    try:
        if server_process and not intentional_stop:
            if server_online:
                # Server is fully online
                await bot.change_presence(
                    activity=Activity(type=ActivityType.playing, name="Minecraft Server: Online"),
                    status=Status.online
                )
                logger.info("Bot status updated: Minecraft Server: Online")
            else:
                # Server is starting
                await bot.change_presence(
                    activity=Activity(type=ActivityType.playing, name="Minecraft Server: Starting"),
                    status=Status.idle
                )
                logger.info("Bot status updated: Minecraft Server: Starting")
        else:
            # Server is offline
            await bot.change_presence(
                activity=Activity(type=ActivityType.playing, name="Minecraft Server: Offline"),
                status=Status.dnd
            )
            logger.info("Bot status updated: Minecraft Server: Offline")
    except Exception as e:
        logger.error(f"Failed to update bot presence: {e}")
        await send_debug(f"❌ Failed to update bot presence: {e}")

async def send_debug(msg: str):
    """Send a debug message to the debug channel and log it."""
    logger.info(f"[DEBUG] {msg}")
    ch = bot.get_channel(DEBUG_CHANNEL_ID)
    if ch:
        try:
            await ch.send(f"[DEBUG] {msg}")
        except Exception as e:
            logger.error(f"Failed to send debug message: {e}")

def rcon_cmd(cmd):
    """Execute an RCON command on the Minecraft server."""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as m:
            return m.command(cmd)
    except Exception as e:
        error_msg = f"RCON failed ({cmd}): {e}"
        logger.error(error_msg)
        asyncio.create_task(send_debug(error_msg))
        return "❌ Server is not running or RCON is unavailable"
        
def map_key(key):
    """Map user input to Minecraft stat key format."""
    return f"minecraft:{key.lower()}"

def display_key(key):
    """Remove 'minecraft:' prefix for display."""
    if key.startswith("minecraft:"):
        return key[10:]
    return key


async def start_server(interaction=None):
    global intentional_stop, restart_attempts, restart_failed, server_process, server_start_time, server_online
    if is_server_process_running():
        logger.info("Server is already running, not starting a new process")
        if interaction:
            await interaction.followup.send("✅ Server is already running.", ephemeral=True)
        return True

    subprocess.run(["screen", "-S", "minecraft", "-X", "quit"], check=False)
    logger.info("Terminated any existing 'minecraft' screen session")

    JAVA_PATH = config.get("java_path", "java")
    session_name = "minecraft"
    java_cmd = f"cd {SERVER_DIR} && {JAVA_PATH} -Xms{JAVA_XMS} -Xmx{JAVA_XMX} -jar {SERVER_JAR} nogui"
    cmd = ["screen", "-dmS", session_name, "bash", "-c", java_cmd]

    jar_path = os.path.join(SERVER_DIR, SERVER_JAR)
    if not os.path.exists(jar_path):
        logger.error(f"Server JAR not found: {jar_path}")
        await send_debug(f"❌ Server JAR not found: {jar_path}")
        if interaction:
            await interaction.followup.send("❌ Server JAR not found.", ephemeral=True)
        return False

    try:
        java_version = subprocess.check_output([JAVA_PATH, "-version"], stderr=subprocess.STDOUT, text=True)
        logger.info(f"Java version: {java_version.strip()}")
    except Exception as e:
        logger.error(f"Java not accessible: {e}")
        await send_debug(f"❌ Java not accessible: {e}")
        if interaction:
            await interaction.followup.send("❌ Java not accessible.", ephemeral=True)
        return False

    try:
        server_process = subprocess.Popen(cmd, cwd=SERVER_DIR)
        server_start_time = datetime.now()
        server_online = False  # Server is starting
        logger.info(f"Server started in screen session 'minecraft' with PID {server_process.pid}")
        await send_debug(f"✅ Server started in screen session `minecraft` with PID {server_process.pid}")
        await update_bot_presence()  # Update status to Starting
    except Exception as e:
        logger.error(f"Failed to start server in screen: {e}")
        await send_debug(f"❌ Failed to start server: {e}")
        if interaction:
            await interaction.followup.send("❌ Failed to start server.", ephemeral=True)
        return False

    await asyncio.sleep(10)
    if not is_server_process_running():
        logger.error("Server process not found after startup")
        await send_debug("❌ Server crashed immediately after startup")
        server_process = None
        server_start_time = None
        server_online = False
        await update_bot_presence()  # Update status to Offline
        if interaction:
            await interaction.followup.send("❌ Server crashed immediately.", ephemeral=True)
        return False

    intentional_stop = False
    restart_attempts = 0
    restart_failed = False
    save_server_state()
    return True

def check_cooldown(user_id, cmd, cd):
    """Check if a command is on cooldown for a user."""
    now = datetime.now()
    last = last_used.get((user_id, cmd))
    if last and (now - last).total_seconds() < cd:
        return False, cd - (now - last).total_seconds()
    last_used[(user_id, cmd)] = now
    return True, 0

def do_backup():
    """Create a backup of the Minecraft world."""
    backup_folder = os.path.join(SERVER_DIR, 'backups')
    old_folder    = os.path.join(backup_folder, 'old')
    os.makedirs(backup_folder, exist_ok=True)
    os.makedirs(old_folder, exist_ok=True)

    today = datetime.now().strftime('%d-%m-%Y')
    dst = os.path.join(backup_folder, f"world_{today}.zip")

    tmp = os.path.join(SERVER_DIR, 'world_tmp')
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    shutil.copytree(os.path.join(SERVER_DIR, WORLD_FOLDER), tmp)

    shutil.make_archive(base_name=dst[:-4], format='zip', root_dir=tmp)
    shutil.rmtree(tmp)
    logger.info(f"Backup created: {dst}")

    now = datetime.now()
    for fname in os.listdir(backup_folder):
        fpath = os.path.join(backup_folder, fname)
        if fname.endswith('.zip') and os.path.isfile(fpath):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if (now - mtime).days > BACKUP_RETENTION_DAYS:
                shutil.move(fpath, os.path.join(old_folder, fname))
                logger.info(f"Moved to old/: {fname}")

    zips = sorted(
        [f for f in os.listdir(backup_folder) if f.endswith('.zip')],
        key=lambda x: os.path.getmtime(os.path.join(backup_folder, x))
    )
    while len(zips) > BACKUP_RETENTION_DAYS:
        rm = zips.pop(0)
        os.remove(os.path.join(backup_folder, rm))
        logger.info(f"Deleted extra backup: {rm}")

async def kill_java_with_lock():
    """Kill any Java processes running the server."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if (
                proc.info['name'] == 'java'
                and 'server.jar' in ' '.join(proc.info['cmdline'])
            ):
                proc.kill()
                await send_debug(f"🔪 Killed Java process PID {proc.info['pid']}")
        except Exception as e:
            await send_debug(f"⚠️ Could not kill process: {e}")
        
async def wait_for_server_stop(interaction=None):
    """Wait until the server process has stopped by checking RCON availability."""
    max_attempts = 30  # 60 seconds total, checking every 2 seconds
    for attempt in range(max_attempts):
        try:
            with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT):
                pass  # Connection succeeded, server is still running
        except Exception:
            # RCON connection failed, server has stopped
            await send_debug("🛑 Server has stopped")
            return  # Exit immediately upon stop
        await asyncio.sleep(2)
    await send_debug("⚠️ Server did not stop within timeout")
    if interaction:
        await interaction.followup.send("⚠️ Server did not stop within timeout", ephemeral=True)

def get_uuid(username):
    """Retrieve a player's UUID from usercache.json."""
    usercache_path = os.path.join(SERVER_DIR, 'usercache.json')
    if not os.path.exists(usercache_path):
        return None
    with open(usercache_path, 'r') as f:
        users = json.load(f)
    for user in users:
        if user['name'].lower() == username.lower():
            return user['uuid']
    return None

def get_server_version():
    """Extract the server version from the latest log file."""
    log_path = os.path.join(SERVER_DIR, 'logs', 'latest.log')
    if not os.path.exists(log_path):
        return "Unknown"
    with open(log_path, 'r') as f:
        for line in f:
            if "Starting minecraft server version" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith('1.') or part.startswith('2.'):
                        return part
    return "Unknown"

def is_server_process_running():
    """Check if the server process is running, kill extras, and handle multiple instances."""
    pids = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            if (
                proc.info['name'] == 'java'
                and SERVER_JAR in ' '.join(proc.info['cmdline'])
                and proc.info['cwd'] == SERVER_DIR
                and proc.is_running()
            ):
                pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if pids:
        if len(pids) > 1:
            pid_list = ", ".join(map(str, pids))
            logger.warning(f"Multiple server instances found: {pid_list}. Terminating extras.")
            for pid in pids[1:]:
                psutil.Process(pid).kill()
                logger.info(f"Killed extra PID {pid}")
                asyncio.create_task(send_debug(f"🔪 Killed extra PID {pid}"))
        return True
    return False
    
async def stats_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice]:
    """Provide autocomplete suggestions for the category parameter."""
    username = interaction.namespace.username
    if not username:
        return []

    # Get UUID and load stats
    uuid = get_uuid(username)
    if not uuid:
        return []

    stats_path = os.path.join(SERVER_DIR, WORLD_FOLDER, 'stats', f"{uuid}.json")
    if not os.path.exists(stats_path):
        return []

    with open(stats_path, 'r') as f:
        stats_data = json.load(f)

    # Extract and filter categories
    categories = [display_key(key) for key in stats_data.get("stats", {}).keys()]
    if not categories:
        return []

    # Filter based on current input
    current = current.lower()
    matches = [cat for cat in categories if current in cat.lower()][:25]  # Limit to 25 choices

    return [app_commands.Choice(name=cat, value=cat) for cat in matches]

async def item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice]:
    """Provide autocomplete suggestions for the item parameter based on the selected category."""
    username = interaction.namespace.username
    category = interaction.namespace.category
    if not username or not category:
        return []

    # Get UUID and load stats
    uuid = get_uuid(username)
    if not uuid:
        return []

    stats_path = os.path.join(SERVER_DIR, WORLD_FOLDER, 'stats', f"{uuid}.json")
    if not os.path.exists(stats_path):
        return []

    with open(stats_path, 'r') as f:
        stats_data = json.load(f)

    # Get items for the selected category
    full_category = map_key(category)
    category_data = stats_data.get("stats", {}).get(full_category, {})
    if not category_data:
        return []

    # Extract and filter items
    items = [display_key(key) for key in category_data.keys()]
    if not items:
        return []

    # Filter based on current input
    current = current.lower()
    matches = [item for item in items if current in item.lower()][:25]  # Limit to 25 choices

    return [app_commands.Choice(name=item, value=item) for item in matches]

# --- Scheduled Tasks ---
@tasks.loop(seconds=CRASH_CHECK_INTERVAL)
async def crash_check():
    global restart_attempts, restart_failed, server_process, server_start_time, server_online
    if not is_server_process_running() and not intentional_stop:
        if restart_attempts < MAX_RESTART_ATTEMPTS:
            await send_debug("⚠️ Server process not found — attempting restart…")
            try:
                await asyncio.get_event_loop().run_in_executor(None, do_backup)
                await kill_java_with_lock()
                session_lock_path = os.path.join(SERVER_DIR, WORLD_FOLDER, "session.lock")
                if os.path.exists(session_lock_path):
                    os.remove(session_lock_path)
                    await send_debug("🧹 Removed leftover session.lock")
                server_process = None
                server_start_time = None
                server_online = False
                await update_bot_presence()  # Update status to Offline
                success = await start_server()
                if success:
                    restart_attempts += 1
                    await send_debug(f"✅ Auto-restarted after failure (attempt {restart_attempts})")
                else:
                    await send_debug(f"❌ <@&{ADMIN_ROLE_ID}> Restart attempt failed: Server failed to start")
            except Exception as e:
                await send_debug(f"❌ <@&{ADMIN_ROLE_ID}> Restart attempt failed: {e}")
        elif not restart_failed:
            restart_failed = True
            server_process = None
            server_start_time = None
            server_online = False
            await update_bot_presence()  # Update status to Offline
            await send_debug(f"🛑 <@&{ADMIN_ROLE_ID}> Restart limit reached ({restart_attempts} attempts). Not restarting.")
                
@tasks.loop(seconds=1)
async def monitor_server_log(interaction=None):
    """Monitor the latest.log file for player join/leave events and server startup."""
    global server_online
    log_path = os.path.join(SERVER_DIR, 'logs', 'latest.log')
    last_position = 0
    join_pattern = re.compile(r'\[.*?\] \[Server thread/INFO\]: (\w+) joined the game')
    leave_pattern = re.compile(r'\[.*?\] \[Server thread/INFO\]: (\w+) left the game')
    done_pattern = re.compile(r'\[.*?\] \[Server thread/INFO\]: Done \([\d.]+s\)! For help')
    
    # Timeout for server startup (5 minutes)
    start_time = time.time()
    timeout = 300  # 300 seconds = 5 minutes

    while True:
        try:
            if not os.path.exists(log_path):
                await send_debug("⚠️ latest.log not found, waiting...")
                if interaction and time.time() - start_time > timeout:
                    await interaction.followup.send("❌ Server failed to start: Log file not found.", ephemeral=True)
                    break
                await asyncio.sleep(10)
                continue

            current_size = os.path.getsize(log_path)
            if current_size < last_position:
                last_position = 0
                await send_debug("🔄 Detected log rotation, resetting position")

            async with aiofiles.open(log_path, mode='r', encoding='utf-8') as f:
                await f.seek(last_position)
                lines = await f.readlines()
                if lines:
                    for line in lines:
                        # Check for join event
                        join_match = join_pattern.search(line)
                        if join_match:
                            player = join_match.group(1)
                            await send_debug(f"🚪 {player} has joined the server")
                        # Check for leave event
                        leave_match = leave_pattern.search(line)
                        if leave_match:
                            player = leave_match.group(1)
                            await send_debug(f"🚶 {player} has left the server")
                        # Check for server ready
                        done_match = done_pattern.search(line)
                        if done_match and not server_online:
                            server_online = True
                            await send_debug("✅ Server is now online")
                            await update_bot_presence()
                            if interaction:
                                await interaction.followup.send("✅ Server turned on.", ephemeral=True)
                                break  # Exit the loop after notifying the user

                    last_position = await f.tell()

            # Check for timeout if waiting for server start
            if interaction and time.time() - start_time > timeout:
                await interaction.followup.send("❌ Server failed to start within 5 minutes.", ephemeral=True)
                break

            await asyncio.sleep(1)
        except Exception as e:
            await send_debug(f"⚠️ Error monitoring server log: {e}")
            if interaction:
                await interaction.followup.send(f"❌ Error monitoring server log: {e}", ephemeral=True)
                break
            await asyncio.sleep(10)

@tasks.loop(time=dt_time(*map(int, BACKUP_TIME.split(':'))))
async def daily_backup():
    """Perform a daily backup at the specified time."""
    await send_debug("Running scheduled backup")
    await asyncio.get_event_loop().run_in_executor(None, do_backup)

@tasks.loop(time=dt_time(*map(int, RESTART_TIME.split(':'))))
async def nightly_restart():
    global server_process, server_start_time, server_online
    res = rcon_cmd("list")
    try:
        count = int(res.split()[2].split('/')[0])
    except:
        count = None
    if count == 0:
        await send_debug("Nightly restart: no players")
        if is_server_process_running():
            rcon_cmd("stop")
            await asyncio.sleep(RESTART_DELAY)
            server_process = None
            server_start_time = None
            server_online = False
            await update_bot_presence()  # Update status to Offline
        await start_server()
        await send_debug("Nightly restart done")

# --- Events ---
@bot.event
async def setup_hook():
    """Setup command tree and sync commands to the guild."""
    logger.info("=== Bot Startup: Syncing Commands ===")
    commands_in_tree = [cmd.name for cmd in bot.tree.get_commands()]
    logger.info(f"Commands in tree before sync: {', '.join(commands_in_tree)}")
    
    guild = discord.Object(id=GUILD_ID)
    max_retries = 5
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Syncing commands to guild {GUILD_ID} (attempt {attempt + 1}/{max_retries})")
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            synced_commands = [cmd.name for cmd in synced]
            logger.info(f"Slash commands synced: {len(synced)} commands [{', '.join(synced_commands)}]")
            await send_debug(f"✅ Synced {len(synced)} commands: {', '.join(synced_commands)}")
            break
        except Exception as e:
            logger.error(f"Guild sync failed: {e}")
            await send_debug(f"Guild sync failed: {e}")
            await asyncio.sleep(10)

@bot.event
async def on_ready():
    global intentional_stop, server_online
    logger.info("=== Bot Connected ===")
    intentional_stop = load_server_state()
    if is_server_process_running():
        intentional_stop = False
        server_online = False  # Assume starting until log confirms Done
        save_server_state()
        await send_debug("🖥️ Server is running on bot startup, monitoring enabled")
        await update_bot_presence()  # Set initial status to Starting
    else:
        if not intentional_stop:
            await send_debug("🚀 Server was not running and intentional_stop was False; starting server")
            await start_server()
        else:
            await send_debug("⏹️ Server not running and intentionally stopped, awaiting /start command")
            await update_bot_presence()  # Set initial status to Offline
    crash_check.start()
    daily_backup.start()
    nightly_restart.start()
    monitor_server_log.start()  # Start log monitoring without interaction

# --- Command Checks ---
def in_command_channel():
    """Ensure commands are used in the designated channel."""
    async def predicate(interaction):
        if interaction.channel_id != COMMAND_CHANNEL_ID:
            await send_debug(f"Check failed: {interaction.user.mention} used command in channel {interaction.channel_id}, expected {COMMAND_CHANNEL_ID}")
            await interaction.response.send_message(f"Use <#{COMMAND_CHANNEL_ID}>", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

def has_role(cmd_name):
    """Check if the user has the required role for a command."""
    async def predicate(interaction):
        user_role_ids = [str(role.id) for role in interaction.user.roles]
        for role_id in user_role_ids:
            if cmd_name in config['roles'].get(role_id, []):
                return True
        await send_debug(f"Check failed: {interaction.user.mention} lacks role for command '{cmd_name}'. User roles: {user_role_ids}")
        await interaction.response.send_message("❌ Prosim, dobi ustrezno vlogo.", ephemeral=True)
        return False
    return app_commands.check(predicate)

# --- Slash Commands ---
@bot.tree.command(name="start", description="Start the server")
@in_command_channel()
@has_role("start")
async def start(interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        global intentional_stop
        if is_server_process_running():
            await interaction.followup.send("✅ Server is already running.", ephemeral=True)
            return
        intentional_stop = False
        save_server_state()
        success = await start_server(interaction)
        if not success:
            await interaction.followup.send("❌ Failed to start server.", ephemeral=True)
            return
        # Start monitoring the log with the interaction
        asyncio.create_task(monitor_server_log(interaction=interaction))
    except Exception as e:
        error_msg = f"❌ Failed to start server: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="stop", description="Stop the server")
@in_command_channel()
@has_role("stop")
async def stop(interaction):
    try:
        global intentional_stop, server_process, server_start_time, server_online
        await interaction.response.defer(ephemeral=True)
        if is_server_process_running():
            intentional_stop = True
            server_online = False  # Server is stopping
            save_server_state()
            await send_debug("Attempting to stop server via RCON")
            rcon_cmd("stop")
            await interaction.followup.send("🛑 Stopping...", ephemeral=True)
            await wait_for_server_stop(interaction)
            server_process = None
            server_start_time = None
            await update_bot_presence()  # Update status to Offline
            await interaction.edit_original_response(content="🛑 Server stopped")
        else:
            await interaction.followup.send("✅ Not running.", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to stop server: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="restart", description="Restart the server")
@in_command_channel()
@has_role("restart")
async def restart(interaction):
    try:
        global intentional_stop, server_process, server_start_time, server_online
        await interaction.response.defer(ephemeral=True)
        async with restart_lock:
            intentional_stop = True
            server_online = False
            save_server_state()
            if is_server_process_running():
                rcon_cmd("stop")
                await asyncio.sleep(RESTART_DELAY)
                server_process = None
                server_start_time = None
                await update_bot_presence()  # Update status to Offline
            success = await start_server(interaction)
            if success:
                await interaction.followup.send("🚀 Restarted.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to restart server.", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to restart server: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="force_restart", description="Force restart server")
@in_command_channel()
@has_role("force_restart")
async def force_restart(interaction):
    try:
        global intentional_stop, server_process, server_start_time, server_online
        await interaction.response.defer(ephemeral=True)
        async with restart_lock:
            intentional_stop = True
            server_online = False
            save_server_state()
            if is_server_process_running():
                rcon_cmd("stop")
                await asyncio.sleep(RESTART_DELAY)
                server_process = None
                server_start_time = None
                await update_bot_presence()  # Update status to Offline
            success = await start_server(interaction)
            if success:
                await interaction.followup.send("🚀 Forced restart done.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to force restart.", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to force restart: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="status", description="Show Minecraft server status")
@in_command_channel()
@has_role("status")
async def status(interaction):
    try:
        ok, wait = check_cooldown(interaction.user.id, "status", STATUS_COOLDOWN)
        if not ok:
            await interaction.response.send_message(f"⏳ Wait {int(wait)}s", ephemeral=True)
            return
        
        # Check server mode
        properties_path = os.path.join(SERVER_DIR, 'server.properties')
        online_mode = True
        if os.path.exists(properties_path):
            with open(properties_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('online-mode='):
                        online_mode = line.strip().split('=')[1].lower() == 'true'
                        break
        
        embed = discord.Embed(title="Minecraft Server Status")
        if server_process and not intentional_stop and server_online:
            # Server is online
            embed.color = 0x00FF00  # Green

            players_response = rcon_cmd("list")
            if "There are" not in players_response:
                await interaction.response.send_message("❌ No players online or server unavailable.", ephemeral=True)
                return

            # Extract numbers using regex
            numbers = re.findall(r'\d+', players_response)
            if len(numbers) >= 2:
                current_players = numbers[0]  # First number is current players
                max_players = numbers[1]      # Second number is max players
            else:
                current_players = "0"
                max_players = "Unknown"

            # Extract player names after the colon
            if ":" in players_response:
                parts = players_response.split(":")
                player_names = parts[1].strip().split(", ") if len(parts) > 1 and parts[1].strip() else []
            else:
                player_names = []

            formatted = f"There are {current_players}/{max_players}: {', '.join(player_names) if player_names else 'None'}"

            # Get TPS
            try:
                tps_raw = rcon_cmd("tps")
                if "Unknown or incomplete command" in tps_raw:
                    tps = "N/A"
                else:
                    try:
                        tps_value = float(tps_raw.split(",")[0].split()[-1])
                        tps = f"{tps_value:.1f}"
                    except (IndexError, ValueError):
                        tps = "N/A"
            except:
                tps = "N/A"

            mem = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent()

            if server_start_time:
                diff = datetime.now() - server_start_time
                uptime = f"{diff.days}d {diff.seconds // 3600}h {(diff.seconds % 3600) // 60}m"
            else:
                uptime = "N/A"
            
            embed.add_field(name="Status", value="✅ Online", inline=False)
            embed.add_field(name="Players", value=formatted, inline=False)
            embed.add_field(name="TPS", value=tps, inline=False)
            embed.add_field(name="RAM %", value=f"{mem}%", inline=False)
            embed.add_field(name="CPU %", value=f"{cpu}%", inline=False)
            embed.add_field(name="Uptime", value=uptime, inline=False)

        elif server_process and not intentional_stop:
            # Server is starting
            embed.color = 0xFFFF00  # Yellow
            embed.add_field(name="Status", value="⚠️ Starting...", inline=False)
        else:
            # Server is offline
            embed.color = 0xFF0000  # Red
            embed.add_field(name="Status", value="❌ Offline", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        error_msg = f"❌ Failed to get status: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)




@bot.tree.command(name="backup_now", description="Trigger a backup now")
@in_command_channel()
@has_role("backup_now")
async def backup_now(interaction):
    """Trigger an immediate backup."""
    try:
        ok, wait = check_cooldown(interaction.user.id, "backup_now", STATUS_COOLDOWN)
        if not ok:
            await interaction.response.send_message(f"⏳ Wait {int(wait)}s", ephemeral=True)
            return
        await interaction.response.send_message("💾 Backing up...", ephemeral=True)
        await asyncio.get_event_loop().run_in_executor(None, do_backup)
        await interaction.followup.send("✅ Backup done.", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to backup: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="reload_config", description="Reload config.json")
@in_command_channel()
@has_role("reload_config")
async def reload_config(interaction):
    """Reload the configuration from config.json."""
    try:
        global config
        with open('config.json', 'r') as f:
            config = json.load(f)
        await interaction.response.send_message("🔄 Config reloaded.", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to reload config: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="shutdown", description="Shutdown the bot and the server")
@in_command_channel()
@has_role("shutdown")
async def shutdown(interaction):
    """Shutdown the Discord bot and the Minecraft server."""
    try:
        await interaction.response.defer(ephemeral=True)
        global intentional_stop, rcon_ready_task
        
        intentional_stop = True
        save_server_state()
        
        message = ""
        
        if is_server_process_running():
            message += "Sending stop command to server via RCON...\n"
            rcon_cmd("stop")
            message += "Waiting for server to stop...\n"
            timeout = 60
            start_time = datetime.now()
            while is_server_process_running():
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    message += "Timeout reached, server did not stop.\n"
                    break
                await asyncio.sleep(1)
            if not is_server_process_running():
                message += "Server has stopped.\n"
            else:
                message += "Server did not stop within timeout.\n"
        else:
            message += "Server is not running.\n"
        
        if rcon_ready_task is not None and not rcon_ready_task.done():
            rcon_ready_task.cancel()
            message += "Cancelled RCON readiness task.\n"
        
        message += "Shutting down bot...\n"
        await interaction.followup.send(message, ephemeral=True)
        await bot.close()
        
    except Exception as e:
        error_msg = f"❌ Failed to shutdown: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="logs", description="Show last N log lines in the log channel")
@in_command_channel()
@has_role("logs")
async def logs(interaction, lines: int = LOG_LINES_DEFAULT):
    """Send the last N lines of the server log to the log channel."""
    try:
        ok, wait = check_cooldown(interaction.user.id, "logs", LOGS_COOLDOWN)
        if not ok:
            await interaction.response.send_message(f"⏳ Wait {int(wait)}s", ephemeral=True)
            return
        path = os.path.join(SERVER_DIR, 'logs', 'latest.log')
        dq = deque(maxlen=lines)
        with open(path) as f:
            for L in f:
                dq.append(L.rstrip())
        log_message = "```" + "\n".join(dq) + "```"
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📜 Last {lines} lines of server log:\n{log_message}")
            await interaction.response.send_message("✅ Logs sent to the log channel.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Log channel not found.", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to get logs: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="whitelist_add", description="Add user to whitelist")
@in_command_channel()
@has_role("whitelist_add")
async def whitelist_add(interaction, username: str):
    try:
        ok, wait = check_cooldown(interaction.user.id, "whitelist_add", STATUS_COOLDOWN)
        if not ok:
            await interaction.response.send_message(f"⏳ Wait {int(wait)}s", ephemeral=True)
            return

        # Get current whitelist
        lst = rcon_cmd("whitelist list")
        if "There are 0 whitelisted players" in lst:
            current_whitelist = []
        else:
            start = lst.find(":") + 1
            players_str = lst[start:].strip()
            current_whitelist = [p.strip() for p in players_str.split(",")]

        # Check if username is already whitelisted (exact match)
        if username in current_whitelist:
            await interaction.response.send_message(f"✅ {username} already whitelisted.", ephemeral=True)
            return

        # Add to whitelist and reload
        res = rcon_cmd(f"whitelist add {username}")
        rcon_cmd("whitelist reload")

        # Get updated whitelist
        lst_after = rcon_cmd("whitelist list")
        if "There are 0 whitelisted players" in lst_after:
            current_whitelist_after = []
        else:
            start_after = lst_after.find(":") + 1
            players_str_after = lst_after[start_after:].strip()
            current_whitelist_after = [p.strip() for p in players_str_after.split(",")]

        # Get UUID from whitelist.json (exact match)
        whitelist_path = os.path.join(SERVER_DIR, 'whitelist.json')
        with open(whitelist_path, 'r') as f:
            whitelist_data = json.load(f)
        uuid = next((entry['uuid'] for entry in whitelist_data if entry['name'] == username), "Unknown")

        # Log and notify
        logger.info(f"Whitelisted {username} with UUID {uuid}. Current whitelist: {', '.join(current_whitelist_after)}")
        await send_debug(f"Whitelisted {username} with UUID {uuid}. Current whitelist: {', '.join(current_whitelist_after)}")
        await interaction.response.send_message(f"➕ {res}", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to whitelist {username}: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="seed", description="Displays the server seed")
@in_command_channel()
@has_role("seed")
async def seed(interaction):
    """Display the server's seed."""
    try:
        seed = rcon_cmd("seed")
        await interaction.response.send_message(f"🌱 {seed}", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to get seed: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="cmd", description="Terminal")
@in_command_channel()
@has_role("cmd")
async def cmd(interaction, command: str):
    """Execute a command via RCON."""
    try:
        res = rcon_cmd(command)
        await interaction.response.send_message(f"Executed: {command}\nResponse: {res}", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Command error: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

import re  # Ensure this is at the top of your file (it already is)

@bot.tree.command(name="players", description="Lists online players")
@in_command_channel()
@has_role("players")
async def players(interaction):
    try:
        players_response = rcon_cmd("list")
        if "There are" not in players_response:
            await interaction.response.send_message("❌ No players online or server unavailable.", ephemeral=True)
            return

        # Extract numbers using regex
        numbers = re.findall(r'\d+', players_response)
        if len(numbers) >= 2:
            current_players = numbers[0]  # First number is current players
            max_players = numbers[1]      # Second number is max players
        else:
            current_players = "0"
            max_players = "Unknown"

        # Extract player names after the colon
        if ":" in players_response:
            parts = players_response.split(":")
            player_names = parts[1].strip().split(", ") if len(parts) > 1 and parts[1].strip() else []
        else:
            player_names = []

        formatted = f"There are {current_players}/{max_players}: {', '.join(player_names) if player_names else 'None'}"
        await interaction.response.send_message(f"👥 {formatted}", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to get players: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)
        
@bot.tree.command(name="bot_stop", description="Stop the bot without affecting the Minecraft server")
@in_command_channel()
@has_role("bot_stop")
async def bot_stop(interaction: discord.Interaction):
    """Stop the Python script, leaving the Minecraft server untouched."""
    try:
        logger.info(f"Bot stop requested by {interaction.user.name}")
        await send_debug(f"🛑 Bot stop requested by {interaction.user.name}")
        await interaction.response.send_message("🛑 Stopping bot... You must manually restart it.", ephemeral=True)
        # No interaction with Minecraft server; just exit
        sys.exit(0)
    except Exception as e:
        error_msg = f"❌ Failed to stop bot: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="bot_restart", description="Restart the bot without affecting the Minecraft server")
@in_command_channel()
@has_role("bot_restart")
async def bot_restart(interaction: discord.Interaction):
    """Restart the Python script, leaving the Minecraft server untouched."""
    try:
        logger.info(f"Bot restart requested by {interaction.user.name}")
        await send_debug(f"🔄 Bot restart requested by {interaction.user.name}")
        await interaction.response.send_message("🔄 Restarting bot...", ephemeral=True)
        # No interaction with Minecraft server; restart script
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        error_msg = f"❌ Failed to restart bot: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="stats", description="Displays player statistics. Usage: /stats <username> [category] [item]")
@app_commands.autocomplete(category=stats_autocomplete, item=item_autocomplete)
@in_command_channel()
@has_role("stats")
async def stats(interaction: discord.Interaction, username: str, category: str = None, item: str = None):
    """Display statistics for a specific player dynamically."""
    try:
        # Get UUID from username
        uuid = get_uuid(username)
        if not uuid:
            await interaction.response.send_message(f"❌ Player {username} not found.", ephemeral=True)
            return

        # Construct and check stats file path
        stats_path = os.path.join(SERVER_DIR, WORLD_FOLDER, 'stats', f"{uuid}.json")
        if not os.path.exists(stats_path):
            await interaction.response.send_message(f"❌ Stats for {username} not found.", ephemeral=True)
            return

        # Load stats JSON
        with open(stats_path, 'r') as f:
            stats_data = json.load(f)

        # Handle different cases based on parameters
        if category is None:
            # List all categories dynamically
            categories = [display_key(key) for key in stats_data.get("stats", {}).keys()]
            if not categories:
                await interaction.response.send_message(f"❌ No stats available for {username}.", ephemeral=True)
                return
            categories.sort()
            msg = f"📊 Available stats categories for {username}:\n- " + "\n- ".join(categories)
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            full_category = map_key(category)
            category_data = stats_data.get("stats", {}).get(full_category, {})
            if not category_data:
                await interaction.response.send_message(f"❌ No stats for category '{category}' for {username}.", ephemeral=True)
                return
            category_display = display_key(full_category)

            if item is None:
                # List top 10 items in the specified category
                sorted_items = sorted(category_data.items(), key=lambda x: x[1], reverse=True)[:10]
                msg = f"📊 Stats for {username} in {category_display}:\n"
                for item_key, count in sorted_items:
                    item_display = display_key(item_key)
                    msg += f"- {item_display}: {count}\n"
                if len(category_data) > 10:
                    msg += "... and more\n"
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                # Show specific stat for category:item
                full_item = map_key(item)
                stat = category_data.get(full_item, 0)
                item_display = display_key(full_item)
                msg = f"{username}'s {category_display}:{item_display}: {stat}"
                await interaction.response.send_message(msg, ephemeral=True)

    except Exception as e:
        error_msg = f"❌ Failed to get stats: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)


@bot.tree.command(name="version", description="Displays server version")
@in_command_channel()
@has_role("version")
async def version(interaction):
    """Display the server version."""
    try:
        ver = get_server_version()
        await interaction.response.send_message(f"🛠️ Server version: {ver}", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to get version: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="server_info", description="Displays server information including version, players, and seed")
@in_command_channel()
@has_role("server_info")
async def server_info(interaction):
    try:
        ver = get_server_version()
        players_response = rcon_cmd("list")
        if "There are" in players_response:
            parts = players_response.split(":")
            count_part = parts[0].split()
            count = count_part[2]
            max_players = count_part[6]
            player_names = parts[1].strip().split(", ") if len(parts) > 1 and parts[1].strip() else []
            players = f"There are {count}/{max_players}: {', '.join(player_names) if player_names else 'None'}"
        else:
            players = "No players online or server unavailable."
            
        seed = rcon_cmd("seed")
        embed = discord.Embed(title="Server Information")
        embed.add_field(name="Version", value=ver, inline=False)
        embed.add_field(name="Players", value=players, inline=False)
        embed.add_field(name="Seed", value=seed, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to get server info: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

@bot.tree.command(name="mods", description="Lists installed mods")
@in_command_channel()
@has_role("mods")
async def mods(interaction):
    mods_dir = os.path.join(SERVER_DIR, 'mods')
    if not os.path.exists(mods_dir):
        await interaction.response.send_message("❌ Mods folder not found.", ephemeral=True)
        return
    mods = [f for f in os.listdir(mods_dir) if f.endswith('.jar')]
    if not mods:
        await interaction.response.send_message("🧩 No mods installed.", ephemeral=True)
    else:
        await interaction.response.send_message(f"🧩 Installed mods:\n- " + "\n- ".join(mods), ephemeral=True)

@bot.tree.command(name="help", description="Displays commands you can use based on your roles")
@in_command_channel()
async def help(interaction):
    try:
        # Get user's role IDs
        user_role_ids = [str(role.id) for role in interaction.user.roles]
        # Get commands the user is allowed to use
        allowed_commands = set()
        for role_id in user_role_ids:
            if role_id in config['roles']:
                allowed_commands.update(config['roles'][role_id])
        
        # Create embed with filtered commands
        embed = discord.Embed(title="Bot Commands", description="Commands you can use:")
        for cmd in bot.tree.get_commands():
            if cmd.name in allowed_commands or cmd.name == "help":  # Always show /help
                embed.add_field(name=f"/{cmd.name}", value=cmd.description, inline=False)
        
        if not allowed_commands:
            embed.add_field(name="No Commands", value="You don't have permission to use any commands.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Failed to show help: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)
        
@bot.tree.command(name="sync", description="Manually sync commands")
@in_command_channel()
@has_role("sync")
async def sync(interaction):
    """Manually sync slash commands to the guild."""
    try:
        await interaction.response.defer(ephemeral=True)
        bot.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await send_debug(f"Manual sync triggered by {interaction.user.mention}: {len(synced)} commands synced")
        await interaction.followup.send(f"✅ Synced {len(synced)} commands.", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Sync failed: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="testcmd", description="Test command to verify registration")
@in_command_channel()
async def testcmd(interaction):
    """Test command to verify command registration."""
    try:
        await interaction.response.send_message("✅ Test command works!", ephemeral=True)
    except Exception as e:
        error_msg = f"❌ Testcmd failed: {e}"
        logger.error(error_msg)
        await send_debug(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)

# --- Event Handlers ---
@bot.event
async def on_app_command(interaction):
    """Log when a user calls a slash command."""
    command_name = interaction.command.name if interaction.command else "unknown"
    user = interaction.user
    log_message = f"User {user.name} called /{command_name}"
    logger.info(log_message)
    await send_debug(log_message)
    await bot.process_app_commands(interaction)

@bot.event
async def on_app_command_error(interaction, error):
    """Handle errors for slash commands."""
    user = interaction.user.mention
    cmd = interaction.command.name if interaction.command else "unknown"
    error_msg = str(error)
    await send_debug(f"{user} used /{cmd} → ERROR: {error_msg}")
    
    if not interaction.response.is_done():
        await interaction.response.send_message(f"❌ Error: {error_msg}", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Error: {error_msg}", ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    """Handle errors for legacy commands."""
    if isinstance(error, commands.CheckFailure):
        return
    logger.error(f"Cmd error: {error}")
    await send_debug(f"Cmd error: {error}")

# --- Cleanup ---
def cleanup():
    """Ensure the server is stopped or terminated on bot shutdown."""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as m:
            m.command("stop")
        logger.info("Sent stop command via RCON")
    except Exception as e:
        logger.error(f"Failed to send stop via RCON: {e}")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if (
                    proc.info['name'] == 'java'
                    and 'server.jar' in ' '.join(proc.info['cmdline'])
                ):
                    proc.kill()
                    logger.info(f"Killed Java process PID {proc.info['pid']}")
            except Exception as e:
                logger.error(f"Could not kill process: {e}")

atexit.register(cleanup)

# --- Run the Bot ---
if __name__ == "__main__":
    bot.run(TOKEN)
