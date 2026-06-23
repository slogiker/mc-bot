import os
import asyncio
import zipfile
from datetime import datetime
from src.config import config
from src.logger import logger

class BackupManager:
    def __init__(self):
        # Resolve backup dir relative to the project root properly
        self.backup_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backups'))
        self.auto_dir = os.path.join(self.backup_dir, 'auto')
        self.custom_dir = os.path.join(self.backup_dir, 'custom')
        self._lock = asyncio.Lock()  # Lock to prevent concurrent backups
        
        # Sync initialization is OK here (happens once at startup)
        os.makedirs(self.auto_dir, exist_ok=True)
        os.makedirs(self.custom_dir, exist_ok=True)

    async def create_backup(self, custom_name=None, server=None):
        """
        Creates a backup asynchronously.
        - **Custom**: If a name is provided, it is stored in 'backups/custom/' and never auto-deleted.
        - **Auto**: If no name, it is stored in 'backups/auto/' and subject to 7-day retention policy.
        """
        async with self._lock:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
            
            if custom_name:
                filename = f"backup_custom_{timestamp}_{custom_name}.zip"
                dest_dir = self.custom_dir
            else:
                filename = f"backup_auto_{timestamp}.zip"
                dest_dir = self.auto_dir
                
            dest_path = os.path.join(dest_dir, filename)
            
            logger.info(f"Starting backup: {filename}")
            
            # Disable auto-save and flush to disk if server is running to prevent corruption
            save_disabled = False
            try:
                if server and server.is_running():
                    from src.utils import rcon_cmd
                    logger.info("Server is running, disabling auto-save for backup...")
                    
                    success_off, _ = await rcon_cmd("save-off")
                    success_all, _ = await rcon_cmd("save-all")
                    
                    if not success_off or not success_all:
                        logger.warning("RCON save-off or save-all failed. Backup might be inconsistent.")
                        # Fallback to the old brief wait if RCON failed, just in case
                        await asyncio.sleep(2)
                    else:
                        save_disabled = True
                        from src.log_dispatcher import log_dispatcher
                        # Wait for the server to confirm it finished saving to disk (can take time on slow drives)
                        logger.info("Waiting for world flush to complete...")
                        if not await log_dispatcher.wait_for_pattern("Saved the game", timeout=60):
                            logger.warning("Timed out waiting for 'Saved the game' confirmation. Proceeding anyway.")

                # Run blocking zip operation in a separate thread (always, even if server is offline)
                await asyncio.to_thread(self._zip_world, dest_path)
                logger.info(f"Backup created successfully: {dest_path}")
                
                if not custom_name:
                    await self._cleanup_auto_backups()
                    
                return True, filename, dest_path
            except Exception as e:
                logger.error(f"Backup failed: {e}")
                return False, str(e), None
            finally:
                if save_disabled:
                    from src.utils import rcon_cmd
                    logger.info("Re-enabling auto-save after backup.")
                    _, _ = await rcon_cmd("save-on")

    def _zip_world(self, dest_path):
        """Zips the world folder directly without creating a temp copy."""
        world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
        
        if not os.path.isdir(world_path):
            raise FileNotFoundError(f"World directory not found: {world_path}")
        # Direct zipping - no temp copy (saves disk space and faster)
        with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(world_path):
                for file in files:
                    # Skip session.lock to avoid errors if server is running
                    if file == 'session.lock':
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, world_path)
                    zf.write(file_path, arcname)

    async def _cleanup_auto_backups(self):
        """Deletes auto backups older than retention days."""
        now = datetime.now()
        retention_days = config.BACKUP_RETENTION_DAYS
        
        logger.info("Running backup cleanup...")
        
        # Use asyncio.to_thread for directory listing
        files = await asyncio.to_thread(os.listdir, self.auto_dir)
        
        for fname in files:
            if not fname.endswith('.zip'):
                continue
                
            fpath = os.path.join(self.auto_dir, fname)
            try:
                # Use asyncio.to_thread for file stat operations
                mtime_timestamp = await asyncio.to_thread(os.path.getmtime, fpath)
                mtime = datetime.fromtimestamp(mtime_timestamp)
                if (now - mtime).days > retention_days:
                    await asyncio.to_thread(os.remove, fpath)
                    logger.info(f"Deleted old backup: {fname}")
            except Exception as e:
                logger.error(f"Failed to delete old backup {fname}: {e}")

backup_manager = BackupManager()
