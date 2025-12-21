import discord
from discord.ext import commands, tasks
import asyncio
import os
import re
import aiofiles
import time
import pytz
from datetime import time as dt_time
from src.config import config
from src.logger import logger
from src.utils import send_debug, rcon_cmd

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_position = None
        # DON'T start tasks here - wait for bot to be ready

    async def cog_load(self):
        """Called when cog is loaded - bot might not be ready yet"""
        pass

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks only after bot is fully ready"""
        # Load server state if using TmuxServerManager
        from src.server_tmux import TmuxServerManager
        if isinstance(self.bot.server, TmuxServerManager):
            logger.info("Loading server state...")
            await self.bot.server._load_state()
        
        if not self.crash_check.is_running():
            logger.info("Starting crash_check task...")
            self.crash_check.start()
        
        if not self.monitor_server_log.is_running():
            logger.info("Starting monitor_server_log task...")
            self.monitor_server_log.start()
        
        # Uncomment when ready:
        # if not self.daily_backup.is_running():
        #     self.daily_backup.start()

    def cog_unload(self):
        """Cancel tasks when cog is unloaded"""
        self.crash_check.cancel()
        self.monitor_server_log.cancel()
        # self.daily_backup.cancel()

    @tasks.loop(seconds=config.CRASH_CHECK_INTERVAL)
    async def crash_check(self):
        """Check if server crashed and restart if needed"""
        try:
            if not self.bot.server.is_running() and not self.bot.server.is_intentionally_stopped():
                logger.warning("⚠️ Server process not found and not intentionally stopped. Attempting restart...")
                await send_debug(self.bot, "⚠️ Server process not found — attempting restart…")
                success = await self.bot.server.start()
                if success:
                    await send_debug(self.bot, "✅ Auto-restarted after failure.")
                else:
                    await send_debug(self.bot, "❌ Restart attempt failed.")
        except Exception as e:
            logger.error(f"Error in crash_check: {e}")

    @crash_check.before_loop
    async def before_crash_check(self):
        """Wait for bot to be ready before starting crash checks"""
        await self.bot.wait_until_ready()
        logger.info("Crash check task is now active")

    @tasks.loop(seconds=1)
    async def monitor_server_log(self):
        """Monitor server logs for player join/leave events"""
        log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
        if not os.path.exists(log_path):
            return

        # Initialize position on first run
        if self.log_position is None:
            try:
                self.log_position = os.path.getsize(log_path)
                logger.info(f"Log monitor initialized at position {self.log_position}")
            except Exception as e:
                logger.error(f"Failed to initialize log position: {e}")
                return

        try:
            current_size = os.path.getsize(log_path)
            
            # Log rotation detection
            if current_size < self.log_position:
                self.log_position = 0
                logger.info("Log rotation detected. Resetting position.")
            
            # Read new lines if file grew
            if current_size > self.log_position:
                async with aiofiles.open(log_path, mode='r', encoding='utf-8', errors='ignore') as f:
                    await f.seek(self.log_position)
                    lines = await f.readlines()
                    self.log_position = await f.tell()

                    for line in lines:
                        await self._process_log_line(line)

        except Exception as e:
            logger.error(f"Error monitoring log: {e}")

    @monitor_server_log.before_loop
    async def before_monitor_log(self):
        """Wait for bot to be ready before monitoring logs"""
        await self.bot.wait_until_ready()
        logger.info("Log monitor task is now active")

    async def _process_log_line(self, line: str):
        """Process a single log line for events"""
        try:
            # Player joined
            if "joined the game" in line:
                match = re.search(r': (\w+) joined the game', line)
                if match:
                    player = match.group(1)
                    await self.send_log(f"🚪 **{player}** joined the server")
            
            # Player left
            elif "left the game" in line:
                match = re.search(r': (\w+) left the game', line)
                if match:
                    player = match.group(1)
                    await self.send_log(f"🚶 **{player}** left the server")

            # Server finished starting
            elif "Done" in line and "For help" in line:
                await self.send_log("✅ Server is **ONLINE**!")
                await self.bot.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Online"),
                    status=discord.Status.online
                )

        except Exception as e:
            logger.error(f"Error processing log line: {e}")

    async def send_log(self, msg: str):
        """Send message to log channel"""
        try:
            channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            if channel:
                await channel.send(msg)
        except Exception as e:
            logger.error(f"Failed to send log message: {e}")

    @tasks.loop(time=dt_time(22, 0, tzinfo=pytz.timezone(config.TIMEZONE)))
    async def daily_backup(self):
        """Create daily backup at scheduled time"""
        try:
            from src.backup_manager import backup_manager
            logger.info("Running scheduled daily backup...")
            success, result = await backup_manager.create_backup()
            if success:
                await self.send_log(f"✅ Daily backup created: `{result}`")
            else:
                await self.send_log(f"❌ Daily backup failed: {result}")
        except Exception as e:
            logger.error(f"Error in daily_backup: {e}")

    @daily_backup.before_loop
    async def before_daily_backup(self):
        """Wait for bot to be ready before scheduling backups"""
        await self.bot.wait_until_ready()
        logger.info("Daily backup task is now active")

async def setup(bot):
    await bot.add_cog(Tasks(bot))
