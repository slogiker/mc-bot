import discord
from discord.ext import commands, tasks
import asyncio
import asyncio.subprocess
import subprocess
import os
from src.config import config
from src.logger import logger
from src.utils import send_debug, rcon_cmd

class Tasks(commands.Cog):
    def __init__(self, bot):
        """
        Initializes the Tasks cog.

        Args:
            bot: The bot instance.
        """
        self.bot = bot
        self.restart_attempts = 0 # Counter for Minecraft server restart failures
        self.playit_restart_attempts = 0 # Counter for Playit tunnel restart failures
        # DON'T start tasks here - wait for bot to be ready

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks only after bot is fully ready"""
        # Load server state if using TmuxServerManager
        from src.server_tmux import TmuxServerManager
        if isinstance(self.bot.server, TmuxServerManager):
            logger.info("Loading server state...")
            await self.bot.server._load_state()
        
        # Clear stale online_players if server is not running at startup
        if not self.bot.server.is_running():
            bot_cfg = config.load_bot_config()
            if bot_cfg.get('online_players'):
                bot_cfg['online_players'] = []
                config.save_bot_config(bot_cfg)
                logger.info("Cleared stale online_players list on startup.")

        if not self.crash_check.is_running():
            logger.info("Starting crash_check task...")
            self.crash_check.start()
        
        

    def cog_unload(self):
        """Cancel tasks when cog is unloaded"""
        self.crash_check.cancel()

    async def _handle_server_crash(self):
        """Handles logic for detecting and recovering from Minecraft server crashes."""
        # Guard: no server.jar means /setup hasn't been run yet — nothing to restart
        if not os.path.exists(os.path.join(config.SERVER_DIR, config.SERVER_JAR)):
            logger.debug("Server not running and no server.jar found — setup not complete, skipping crash recovery.")
            return

        # Clear stale player list — crash means no "left the game" messages were fired
        bot_config = config.load_bot_config()
        if bot_config.get('online_players'):
            bot_config['online_players'] = []
            config.save_bot_config(bot_config)

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
        
        success, _ = await self.bot.server.start()
        if success:
            await send_debug(self.bot, "Auto-restarted after failure.")
            self.restart_attempts = 0
        else:
            await send_debug(self.bot, f"Restart attempt {self.restart_attempts} failed.")

    @tasks.loop(seconds=config.CRASH_CHECK_INTERVAL)
    async def crash_check(self):
        """Check if server crashed and restart if needed"""
        try:
            if not self.bot.server.is_running() and not self.bot.server.is_intentionally_stopped():
                # Guard: no server.jar means /setup hasn't been run yet — nothing to restart
                if not os.path.exists(os.path.join(config.SERVER_DIR, config.SERVER_JAR)):
                    logger.debug("Server not running and no server.jar found — setup not complete, skipping crash recovery.")
                    return

                logger.info("🚨 Minecraft server crash detected! Attempting auto-restart...")

                # Clear stale player list — crash means no "left the game" messages were fired
                bot_config = config.load_bot_config()
                if bot_config.get('online_players'):
                    bot_config['online_players'] = []
                    config.save_bot_config(bot_config)

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
                
                success, _ = await self.bot.server.start()
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
            secret_key_path = os.path.join(os.getcwd(), "data", "playit_secret.key")
            playit_secret = os.environ.get("PLAYIT_SECRET_KEY") or (open(secret_key_path).read().strip() if os.path.exists(secret_key_path) else None)

            if playit_secret:
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
                                f"Check your Playit configuration or restart manually with `tmux new-session -d -s playit 'playit --platform-docker --secret-path data/playit_secret.key'`."
                            )
                        self.playit_restart_attempts += 1
                        return
                    elif self.playit_restart_attempts > 2:
                        return

                    self.playit_restart_attempts += 1
                    logger.warning(f"Playit tunnel not running. Restart attempt {self.playit_restart_attempts}/2...")
                    await send_debug(self.bot, f"Playit tunnel not running — restart attempt {self.playit_restart_attempts}/2...")
                    
                    # Ensure secret file exists for --secret-path if using ENV
                    if os.environ.get("PLAYIT_SECRET_KEY") and not os.path.exists(secret_key_path):
                        with open(secret_key_path, "w") as f:
                            f.write(os.environ.get("PLAYIT_SECRET_KEY"))

                    socket_path = os.path.join(os.getcwd(), "data", "playit.sock")
                    log_path = os.path.join(os.getcwd(), "logs", "playit.log")

                    start_proc = await asyncio.create_subprocess_exec(
                        "tmux", "new-session", "-d", "-s", "playit",
                        "playit", "--platform-docker", "--secret-path", secret_key_path, "--socket-path", socket_path, "-l", log_path
                    )
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
        # Give the server ample time to initialize on slow hardware (e.g. CM4/Fabric) before we start monitoring for crashes
        await asyncio.sleep(60)
        logger.info("Crash check task is now active")

async def setup(bot):
    await bot.add_cog(Tasks(bot))
