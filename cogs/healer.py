import os
import psutil
from pathlib import Path
from discord.ext import commands, tasks
from src.config import config
from src.logger import logger
from src.utils import send_debug
from src.mod_updater import ModUpdater

class Healer(commands.Cog):
    """
    Self-healing module for automated error recovery and infrastructure maintenance.
    """
    def __init__(self, bot):
        self.bot = bot
        self.maintenance_loop.start()
        self.crash_analyzer_loop.start()
        
    def cog_unload(self):
        self.maintenance_loop.cancel()
        self.crash_analyzer_loop.cancel()

    @tasks.loop(minutes=15)
    async def maintenance_loop(self):
        """Perform infrastructure health checks (Disk, Logs)."""
        try:
            # 1. Disk Space Check
            usage = psutil.disk_usage('/')
            if usage.percent > 90:
                logger.warning(f"🚨 Disk space critical: {usage.percent}% used!")
                await self._cleanup_old_data(usage.percent)
            
            # 2. Log Rotation Check
            # (Handled by logger.py, but we can verify directory sizes here)
            logs_size = sum(f.stat().st_size for f in Path('logs').rglob('*') if f.is_file())
            if logs_size > 500 * 1024 * 1024: # 500MB
                logger.warning("🚨 Logs directory exceeding 500MB. Consider aggressive cleanup.")

        except Exception as e:
            logger.error(f"Healer: maintenance error: {e}")

    async def _cleanup_old_data(self, percent):
        """Automatically delete oldest auto-backups to free space."""
        backup_dir = os.path.join(os.getcwd(), 'backups', 'auto')
        if not os.path.exists(backup_dir):
            return

        files = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.zip')],
            key=os.path.getctime
        )

        if files:
            oldest = files[0]
            os.remove(oldest)
            logger.info(f"Healer: Deleted oldest backup {os.path.basename(oldest)} to free disk space ({percent}% used).")
            await send_debug(self.bot, f"🧹 Self-Healer: Deleted `{os.path.basename(oldest)}` due to low disk space ({percent}%).")

    @tasks.loop(seconds=30)
    async def crash_analyzer_loop(self):
        """Deep log analysis for automated crash repair."""
        if not self.bot.server.is_running() and not self.bot.server.is_intentionally_stopped():
            from src.log_dispatcher import log_dispatcher
            recent_logs = log_dispatcher.get_recent_logs()
            
            for line in reversed(recent_logs):
                # 1. Outdated Plugin Detection
                if "outdated plugin" in line.lower() or "unsupported version" in line.lower():
                    # Attempt to extract plugin name (simplified heuristic)
                    logger.info("Healer: Detected outdated plugin. Triggering ModUpdater repair...")
                    updater = ModUpdater()
                    await updater.update_everything() # Aggressive fix
                    await send_debug(self.bot, "🔧 Self-Healer: Detected plugin version conflict. Updating all mods/plugins...")
                    break
                
                # 2. EULA Failure
                if "You need to agree to the EULA" in line:
                    eula_path = os.path.join(config.SERVER_DIR, 'eula.txt')
                    with open(eula_path, 'w') as f:
                        f.write("eula=true\n")
                    logger.info("Healer: Automatically accepted EULA.")
                    await send_debug(self.bot, "🔧 Self-Healer: Automatically accepted EULA for you.")
                    break

                # 3. Java UnsupportedClassVersionError (Outdated Java Runtime)
                if "java.lang.unsupportedclassversionerror" in line.lower() or "compiled by a more recent version" in line.lower():
                    logger.warning("Healer: Detected Java UnsupportedClassVersionError. Resolving compatible JRE...")
                    from src.jre_manager import jre_manager
                    from src.utils import get_server_version
                    import re
                    class_match = re.search(r'class file version (\d+)', line)
                    needed_java = None
                    if class_match:
                        class_ver = int(class_match.group(1))
                        if class_ver >= 53:
                            needed_java = class_ver - 44
                        elif class_ver == 52:
                            needed_java = 8
                    
                    if not needed_java:
                        detected_ver = await get_server_version()
                        needed_java = jre_manager.get_required_java_version(detected_ver)

                    try:
                        await jre_manager.ensure_jre(needed_java)
                        await send_debug(self.bot, f"☕ Self-Healer: Installed Java {needed_java} to resolve crash. Restarting server...")
                        await self.bot.server.start()
                    except Exception as jre_fix_err:
                        logger.error(f"Healer failed to auto-fix Java mismatch: {jre_fix_err}")
                    break

    @maintenance_loop.before_loop
    @crash_analyzer_loop.before_loop
    async def before_healer(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Healer(bot))
