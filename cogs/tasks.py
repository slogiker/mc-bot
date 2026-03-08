import discord
from discord.ext import commands, tasks
import asyncio
import os
import re
from src.config import config
from src.logger import logger
from src.utils import send_debug, rcon_cmd

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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
        
        # daily_backup is handled by backup.py cog scheduling
        # Uncomment when ready:
        # if not self.daily_backup.is_running():
        #     self.daily_backup.start()

    def cog_unload(self):
        """Cancel tasks when cog is unloaded"""
        self.crash_check.cancel()

    @tasks.loop(seconds=config.CRASH_CHECK_INTERVAL)
    async def crash_check(self):
        """Check if server crashed and restart if needed"""
        try:
            if not self.bot.server.is_running() and not self.bot.server.is_intentionally_stopped():
                # specific check to ensure we update status if it crashed
                if self.bot.status != discord.Status.dnd:
                     await self.bot.change_presence(
                        activity=discord.Activity(type=discord.ActivityType.playing, name="Server Offline"),
                        status=discord.Status.dnd
                    )
                
                logger.warning("Server process not found and not intentionally stopped. Attempting restart...")
                await send_debug(self.bot, "Server process not found -- attempting restart...")
                success = await self.bot.server.start()
                if success:
                    await send_debug(self.bot, "Auto-restarted after failure.")
                else:
                    await send_debug(self.bot, "Restart attempt failed.")
            
            # If intentionally stopped, ensure status is DND/Idle
            elif self.bot.server.is_intentionally_stopped():
                 # We don't want to override if already set, but just to be safe
                 pass 

        except Exception as e:
            logger.error(f"Error in crash_check: {e}")

    @crash_check.before_loop
    async def before_crash_check(self):
        """Wait for bot to be ready before starting crash checks"""
        await self.bot.wait_until_ready()
        logger.info("Crash check task is now active")

    # daily_backup kept but fixed for tuple unpacking
    # Currently commented out in on_ready - backup.py handles scheduling
    async def daily_backup_manual(self):
        """Create daily backup (called manually or by scheduler)"""
        try:
            from src.backup_manager import backup_manager
            logger.info("Running scheduled daily backup...")
            success, filename, filepath = await backup_manager.create_backup()
            if success:
                logger.info(f"Daily backup created: {filename}")
            else:
                logger.error(f"Daily backup failed: {filename}")
        except Exception as e:
            logger.error(f"Error in daily_backup: {e}")

async def setup(bot):
    await bot.add_cog(Tasks(bot))
