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
        self.crash_check.start()
        self.monitor_server_log.start()
        # self.daily_backup.start()
        # self.nightly_restart.start()

    def cog_unload(self):
        self.crash_check.cancel()
        # self.monitor_server_log.cancel()
        # self.daily_backup.cancel()
        # self.nightly_restart.cancel()

    @tasks.loop(seconds=config.CRASH_CHECK_INTERVAL)
    async def crash_check(self):
        if not self.bot.server.is_running() and not self.bot.server.is_intentionally_stopped():
             logger.warning("⚠️ Server process not found and not intentionally stopped. Attempting restart...")
             await send_debug(self.bot, "⚠️ Server process not found — attempting restart…")
             success = await self.bot.server.start()
             if success:
                 await send_debug(self.bot, "✅ Auto-restarted after failure.")
             else:
                 await send_debug(self.bot, f"❌ Restart attempt failed.")

    @tasks.loop(seconds=1)
    async def monitor_server_log(self):
        log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
        if not os.path.exists(log_path):
            return

        # Initialize position if not set
        if not hasattr(self, 'log_position'):
            self.log_position = os.path.getsize(log_path)
            logger.info(f"Log monitor started. Seeking to end of file ({self.log_position} bytes).")

        try:
            current_size = os.path.getsize(log_path)
            if current_size < self.log_position:
                self.log_position = 0 # Log rotated
                logger.info("Log rotation detected. Resetting position to 0.")
            
            if current_size > self.log_position:
                async with aiofiles.open(log_path, mode='r', encoding='utf-8', errors='ignore') as f:
                    await f.seek(self.log_position)
                    lines = await f.readlines()
                    self.log_position = await f.tell()

                    for line in lines:
                        # Join
                        if "joined the game" in line:
                            match = re.search(r': (\w+) joined the game', line)
                            if match:
                                player = match.group(1)
                                await self.send_log(f"🚪 **{player}** joined the server")
                        
                        # Leave
                        elif "left the game" in line:
                            match = re.search(r': (\w+) left the game', line)
                            if match:
                                player = match.group(1)
                                await self.send_log(f"🚶 **{player}** left the server")

                        # Done
                        elif "Done" in line and "For help" in line:
                             await self.send_log("✅ Server is **ONLINE**!")
                             await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Online"), status=discord.Status.online)

        except Exception as e:
            logger.error(f"Error monitoring log: {e}")

    async def send_log(self, msg):
        channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if channel:
            await channel.send(msg)

    @tasks.loop(time=dt_time(22, 0, tzinfo=pytz.timezone(config.TIMEZONE)))
    async def daily_backup(self):
        from src.backup_manager import backup_manager
        logger.info("Running scheduled daily backup...")
        success, result = await backup_manager.create_backup()
        if success:
             await self.send_log(f"✅ Daily backup created: `{result}`")
        else:
             await self.send_log(f"❌ Daily backup failed: {result}")

async def setup(bot):
    await bot.add_cog(Tasks(bot))
