"""
Tests for src/backup_manager.py — BackupManager
"""
import os
import time
import zipfile
import asyncio
import pytest


class TestBackupManager:
    """Tests for the BackupManager class."""

    def _make_manager(self, backup_dir, server_dir):
        """Create a BackupManager with patched directories."""
        from src.backup_manager import BackupManager
        mgr = BackupManager.__new__(BackupManager)
        mgr.backup_dir = backup_dir
        mgr.auto_dir = os.path.join(backup_dir, "auto")
        mgr.custom_dir = os.path.join(backup_dir, "custom")
        os.makedirs(mgr.auto_dir, exist_ok=True)
        os.makedirs(mgr.custom_dir, exist_ok=True)
        return mgr

    @pytest.mark.asyncio
    async def test_create_auto_backup(self, temp_world_dir, temp_backup_dir):
        """Auto backup creates a zip in the auto/ directory."""
        from src.config import config
        config.SERVER_DIR = temp_world_dir
        config.WORLD_FOLDER = "world"
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, temp_world_dir)
        success, filename, path = await mgr.create_backup()

        assert success is True
        assert filename.startswith("backup_auto_")
        assert path is not None
        assert os.path.exists(path)

        # Verify it's a valid zip
        with zipfile.ZipFile(path, 'r') as zf:
            names = zf.namelist()
            assert "level.dat" in names
            assert "level.dat_old" in names
            # session.lock should be skipped
            assert "session.lock" not in names
            assert "region/r.0.0.mca" in names

    @pytest.mark.asyncio
    async def test_create_custom_backup(self, temp_world_dir, temp_backup_dir):
        """Custom backup goes into custom/ directory with the given name."""
        from src.config import config
        config.SERVER_DIR = temp_world_dir
        config.WORLD_FOLDER = "world"
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, temp_world_dir)
        success, filename, path = await mgr.create_backup(custom_name="my-save")

        assert success is True
        assert "my-save" in filename
        assert "custom" in path
        assert os.path.exists(path)

    @pytest.mark.asyncio
    async def test_cleanup_old_auto_backups(self, temp_backup_dir):
        """Auto backups older than retention days are deleted."""
        from src.config import config
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, "/fake")

        # Create a "old" auto backup file
        old_file = os.path.join(mgr.auto_dir, "backup_auto_old.zip")
        with open(old_file, "w") as f:
            f.write("old backup")

        # Set mtime to 10 days ago
        old_time = time.time() - (10 * 86400)
        os.utime(old_file, (old_time, old_time))

        # Create a "new" auto backup file
        new_file = os.path.join(mgr.auto_dir, "backup_auto_new.zip")
        with open(new_file, "w") as f:
            f.write("new backup")

        await mgr._cleanup_auto_backups()

        assert not os.path.exists(old_file), "Old backup should be deleted"
        assert os.path.exists(new_file), "New backup should survive"

    @pytest.mark.asyncio
    async def test_cleanup_ignores_non_zip(self, temp_backup_dir):
        """Cleanup should not touch non-zip files."""
        from src.config import config
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, "/fake")

        txt_file = os.path.join(mgr.auto_dir, "notes.txt")
        with open(txt_file, "w") as f:
            f.write("keep me")
        old_time = time.time() - (10 * 86400)
        os.utime(txt_file, (old_time, old_time))

        await mgr._cleanup_auto_backups()

        assert os.path.exists(txt_file), "Non-zip files should not be deleted"

    @pytest.mark.asyncio
    async def test_backup_missing_world_fails(self, temp_backup_dir):
        """Backup fails gracefully when world directory doesn't exist."""
        from src.config import config
        config.SERVER_DIR = "/nonexistent/path"
        config.WORLD_FOLDER = "world"
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, "/nonexistent/path")
        success, error_msg, path = await mgr.create_backup()

        assert success is False
        assert path is None
