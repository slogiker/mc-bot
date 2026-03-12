import os
import shutil
import asyncio
import zipfile
from datetime import datetime
from src.config import config
from src.logger import logger
import aiohttp

class BackupManager:
    def __init__(self):
        self.backup_dir = '/app/backups'
        self.auto_dir = os.path.join(self.backup_dir, 'auto')
        self.custom_dir = os.path.join(self.backup_dir, 'custom')
        
        # Sync initialization is OK here (happens once at startup)
        os.makedirs(self.auto_dir, exist_ok=True)
        os.makedirs(self.custom_dir, exist_ok=True)

    async def create_backup(self, custom_name=None):
        """
        Creates a backup asynchronously.
        - **Custom**: If a name is provided, it is stored in 'backups/custom/' and never auto-deleted.
        - **Auto**: If no name, it is stored in 'backups/auto/' and subject to 7-day retention policy.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        
        if custom_name:
            filename = f"backup_custom_{timestamp}_{custom_name}.zip"
            dest_dir = self.custom_dir
        else:
            filename = f"backup_auto_{timestamp}.zip"
            dest_dir = self.auto_dir
            
        dest_path = os.path.join(dest_dir, filename)
        
        logger.info(f"Starting backup: {filename}")
        
        try:
            # Run blocking zip operation in a separate thread
            await asyncio.to_thread(self._zip_world, dest_path)
            logger.info(f"Backup created successfully: {dest_path}")
            
            if not custom_name:
                await self._cleanup_auto_backups()
                
            return True, filename, dest_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False, str(e), None

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

    async def upload_backup(self, filepath):
        """Uploads a backup file using transfer.sh and returns the link."""
        try:
            filename = os.path.basename(filepath)
            url = f"https://transfer.sh/{filename}"
            
            # Using a custom timeout as backups can be large
            timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour max upload time
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                with open(filepath, 'rb') as f:
                    async with session.post(url, data=f) as resp:
                        if resp.status == 200:
                            link = await resp.text()
                            return link.strip()
                        else:
                            logger.error(f"Upload failed with status {resp.status}: {await resp.text()}")
                            return None
        except Exception as e:
            logger.error(f"Failed to upload backup: {e}")
            return None

backup_manager = BackupManager()
