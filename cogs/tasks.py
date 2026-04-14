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
        self.restart_attempts = 0
        self.playit_restart_attempts = 0
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
                
                if self.restart_attempts == 2:
                    logger.error("Server failed to restart twice. Stopping crash loop.")
                    cmd_channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID) if config.COMMAND_CHANNEL_ID else None
                    owner_id = config.OWNER_ID
                    if cmd_channel and owner_id:
                        # Fetch recent logs to determine crash reason
                        from src.log_dispatcher import log_dispatcher
                        recent_logs = log_dispatcher.get_recent_logs()
                        
                        crash_reason = ""
                        # Scan backwards for the first identifiable crash reason
                        for line in reversed(recent_logs):
                            if "OutOfMemoryError" in line:
                                crash_reason = "🚨 **Reason:** The server ran out of RAM (`OutOfMemoryError`). Please increase your maximum RAM via `/settings`."
                                break
                            elif "Killed" in line or "killed by signal" in line:
                                crash_reason = "🚨 **Reason:** The server process was forcefully killed by the host OS (likely OOM killer)."
                                break
                                
                        if not crash_reason and recent_logs:
                            # If no specific error, provide the last 5 lines for context
                            last_few = "\n".join(recent_logs[-5:])
                            crash_reason = f"**Last 5 Log Lines:**\n```\n{last_few}\n```"
                            
                        msg = f"<@{owner_id}> 🚨 The server has crashed and failed to auto-restart completely. The crash loop has been aborted. Check `/logs`.\n\n{crash_reason}"
                        await cmd_channel.send(msg)
                        
                    # Stop checking
                    self.bot.server._intentional_stop = True
                    if hasattr(self.bot.server, '_save_state'):
                        await self.bot.server._save_state()
                        
                    self.restart_attempts += 1
                    return
                elif self.restart_attempts > 2:
                    self.bot.server._intentional_stop = True
                    return
                
                logger.warning("Server process not found and not intentionally stopped. Attempting restart...")
                await send_debug(self.bot, "Server process not found -- attempting restart...")
                self.restart_attempts += 1
                
                success = await self.bot.server.start()
                if success:
                    await send_debug(self.bot, "Auto-restarted after failure.")
                    self.restart_attempts = 0
                else:
                    await send_debug(self.bot, f"Restart attempt {self.restart_attempts} failed.")
            
            # If intentionally stopped, ensure status is DND/Idle
            elif self.bot.server.is_intentionally_stopped():
                 if self.bot.status != discord.Status.dnd:
                     await self.bot.change_presence(
                        activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Offline"),
                        status=discord.Status.dnd
                     ) 

            # Check Playit tunnel (same pattern as MC server crash recovery)
            if os.path.exists("/app/data/playit_secret.key"):
                import subprocess
                proc = await asyncio.create_subprocess_exec("tmux", "has-session", "-t", "playit", stderr=subprocess.DEVNULL)
                await proc.wait()
                playit_running = (proc.returncode == 0)
                
                if not playit_running:
                    if self.playit_restart_attempts == 2:
                        logger.error("Playit tunnel failed to restart twice. Stopping Playit crash loop.")
                        cmd_channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID)
                        owner_id = config.OWNER_ID
                        if cmd_channel and owner_id:
                            await cmd_channel.send(
                                f"<@{owner_id}> 🚨 The Playit tunnel has crashed and failed to auto-restart after 2 attempts. "
                                f"Check your Playit configuration or restart manually with `tmux new-session -d -s playit 'playit --secret $(cat /app/data/playit_secret.key)'`."
                            )
                        self.playit_restart_attempts += 1
                        return
                    elif self.playit_restart_attempts > 2:
                        return

                    self.playit_restart_attempts += 1
                    logger.warning(f"Playit tunnel not running. Restart attempt {self.playit_restart_attempts}/2...")
                    await send_debug(self.bot, f"Playit tunnel not running — restart attempt {self.playit_restart_attempts}/2...")
                    
                    start_proc = await asyncio.create_subprocess_shell('tmux new-session -d -s playit "playit --secret $(cat /app/data/playit_secret.key)"')
                    await start_proc.wait()

                    # Verify it actually started
                    await asyncio.sleep(3)
                    verify_proc = await asyncio.create_subprocess_exec("tmux", "has-session", "-t", "playit", stderr=subprocess.DEVNULL)
                    await verify_proc.wait()
                    if verify_proc.returncode == 0:
                        await send_debug(self.bot, "Playit tunnel restarted successfully.")
                        self.playit_restart_attempts = 0
                    else:
                        await send_debug(self.bot, f"Playit restart attempt {self.playit_restart_attempts} failed.")
                else:
                    # Tunnel is running, reset counter
                    if self.playit_restart_attempts > 0:
                        self.playit_restart_attempts = 0 

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
