import os
import shutil
import asyncio
import zipfile
from datetime import datetime
from src.config import config
from src.logger import logger

class BackupManager:
    def __init__(self):
        self.backup_dir = os.path.join(config.SERVER_DIR, 'backups')
        self.auto_dir = os.path.join(self.backup_dir, 'auto')
        self.custom_dir = os.path.join(self.backup_dir, 'custom')
        
        os.makedirs(self.auto_dir, exist_ok=True)
        os.makedirs(self.custom_dir, exist_ok=True)

    async def create_backup(self, custom_name=None):
        """Creates a backup asynchronously.
        If custom_name is provided, it's a custom backup (kept forever).
        Otherwise, it's an auto backup (subject to retention policy).
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
                
            return True, filename
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False, str(e)

    def _zip_world(self, dest_path):
        """Zips the world folder. This is a blocking operation."""
        world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
        
        # Create a temporary copy to avoid file locking issues (optional but safer)
        # For large worlds, copying might be slow. 
        # Given the user wants "no freeze", copying first is safer but slower.
        # Direct zipping is faster but might hit locked files.
        # Let's try direct zipping with error tolerance or copy-then-zip.
        # The original code did copytree to tmp. Let's stick to that pattern for safety.
        
        tmp_path = os.path.join(config.SERVER_DIR, 'world_tmp_backup')
        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path)
            
        shutil.copytree(world_path, tmp_path)
        
        with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(tmp_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, tmp_path)
                    zf.write(file_path, arcname)
                    
        shutil.rmtree(tmp_path)

    async def _cleanup_auto_backups(self):
        """Deletes auto backups older than retention days."""
        now = datetime.now()
        retention_days = config.BACKUP_RETENTION_DAYS
        
        logger.info("Running backup cleanup...")
        
        for fname in os.listdir(self.auto_dir):
            if not fname.endswith('.zip'):
                continue
                
            fpath = os.path.join(self.auto_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if (now - mtime).days > retention_days:
                    os.remove(fpath)
                    logger.info(f"Deleted old backup: {fname}")
            except Exception as e:
                logger.error(f"Failed to delete old backup {fname}: {e}")

backup_manager = BackupManager()
