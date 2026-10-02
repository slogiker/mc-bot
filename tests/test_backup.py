"""
Tests for src/backup_manager.py - BackupManager
"""
import os
import time
import tarfile
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import zstandard


class TestBackupManager:
    """Tests for the BackupManager class."""

    def _make_manager(self, backup_dir, server_dir):
        """Create a BackupManager with patched directories."""
        from src.backup_manager import BackupManager
        mgr = BackupManager()
        mgr.backup_dir = backup_dir
        mgr.auto_dir = os.path.join(backup_dir, "auto")
        mgr.custom_dir = os.path.join(backup_dir, "custom")
        mgr.logs_dir = os.path.join(backup_dir, "logs")
        mgr.log_file = os.path.join(mgr.logs_dir, "backup.log")
        # Re-create directories in the new temp location
        os.makedirs(mgr.auto_dir, exist_ok=True)
        os.makedirs(mgr.custom_dir, exist_ok=True)
        os.makedirs(mgr.logs_dir, exist_ok=True)
        return mgr

    @pytest.mark.asyncio
    async def test_create_auto_backup(self, temp_world_dir, temp_backup_dir):
        """Auto backup creates a zstd compressed tar archive in the auto/ directory."""
        from src.config import config
        config.SERVER_DIR = temp_world_dir
        # Create server.properties to satisfy the WORLD_FOLDER property
        with open(os.path.join(temp_world_dir, "server.properties"), "w") as f:
            f.write("level-name=world\n")
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, temp_world_dir)
        with patch.object(mgr, '_ship_to_nas', new_callable=AsyncMock) as mock_ship:
            mock_ship.return_value = (True, "")
            success, filename, path = await mgr.create_backup()

        assert success is True
        assert filename.startswith("backup_auto_")
        assert filename.endswith(".tar.zst")
        assert path is not None
        assert os.path.exists(path)

        # Verify it's a valid zstd compressed tar archive
        dctx = zstandard.ZstdDecompressor()
        with open(path, 'rb') as f:
            with dctx.stream_reader(f) as reader:
                with tarfile.open(fileobj=reader, mode='r|') as tf:
                    names = [entry.name for entry in tf]
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
        # Create server.properties to satisfy the WORLD_FOLDER property
        with open(os.path.join(temp_world_dir, "server.properties"), "w") as f:
            f.write("level-name=world\n")
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, temp_world_dir)
        with patch.object(mgr, '_ship_to_nas', new_callable=AsyncMock) as mock_ship:
            mock_ship.return_value = (True, "")
            success, filename, path = await mgr.create_backup(custom_name="my-save")

        assert success is True
        assert "my-save" in filename
        assert filename.endswith(".tar.zst")
        assert "custom" in path
        assert os.path.exists(path)

    @pytest.mark.asyncio
    async def test_cleanup_old_auto_backups(self, temp_backup_dir):
        """Auto backups older than retention days are deleted."""
        from src.config import config
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, "/fake")

        # Create an "old" auto backup file
        old_file = os.path.join(mgr.auto_dir, "backup_auto_old.tar.zst")
        with open(old_file, "w") as f:
            f.write("old backup")

        # Set mtime to 10 days ago
        old_time = time.time() - (10 * 86400)
        os.utime(old_file, (old_time, old_time))

        # Create a "new" auto backup file
        new_file = os.path.join(mgr.auto_dir, "backup_auto_new.tar.zst")
        with open(new_file, "w") as f:
            f.write("new backup")

        await mgr._cleanup_local_backups()

        assert not os.path.exists(old_file), "Old backup should be deleted"
        assert os.path.exists(new_file), "New backup should survive"

    @pytest.mark.asyncio
    async def test_cleanup_ignores_non_archive(self, temp_backup_dir):
        """Cleanup should not touch non-archive files."""
        from src.config import config
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, "/fake")

        txt_file = os.path.join(mgr.auto_dir, "notes.txt")
        with open(txt_file, "w") as f:
            f.write("keep me")
        old_time = time.time() - (10 * 86400)
        os.utime(txt_file, (old_time, old_time))

        await mgr._cleanup_local_backups()

        assert os.path.exists(txt_file), "Non-archive files should not be deleted"

    @pytest.mark.asyncio
    async def test_backup_missing_world_fails(self, temp_backup_dir):
        """Backup fails gracefully when world directory doesn't exist."""
        from src.config import config
        config.SERVER_DIR = "/nonexistent/path"
        config.BACKUP_RETENTION_DAYS = 7

        mgr = self._make_manager(temp_backup_dir, "/nonexistent/path")
        success, error_msg, path = await mgr.create_backup()

        assert success is False
        assert path is None

    @pytest.mark.asyncio
    async def test_nas_shipping_command_shape(self, temp_backup_dir):
        """Verify rsync command shape matches exact specification."""
        mgr = self._make_manager(temp_backup_dir, "/fake")
        dummy_archive = os.path.join(mgr.auto_dir, "backup_auto_2026-10-02_12-00.tar.zst")
        with open(dummy_archive, "w") as f:
            f.write("dummy")

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            success, err = await mgr._ship_to_nas(dummy_archive)

            assert success is True
            assert err == ""
            mock_exec.assert_called_once_with(
                "rsync",
                "-avz",
                "-e",
                "ssh -i ~/.ssh/mc-bot-backup",
                dummy_archive,
                "slogiker@192.168.1.41:/pool-bulk/backups/mc-bot/",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL
            )

    @pytest.mark.asyncio
    async def test_nas_unreachable_fails_gracefully(self, temp_world_dir, temp_backup_dir):
        """If NAS transfer fails, local backup completes and retention cleanup is skipped."""
        from src.config import config
        config.SERVER_DIR = temp_world_dir
        with open(os.path.join(temp_world_dir, "server.properties"), "w") as f:
            f.write("level-name=world\n")

        mgr = self._make_manager(temp_backup_dir, temp_world_dir)

        # Place an old local backup (10 days old, cutoff is 7)
        old_file = os.path.join(mgr.auto_dir, "backup_auto_old.tar.zst")
        with open(old_file, "w") as f:
            f.write("old backup")
        old_time = time.time() - (10 * 86400)
        os.utime(old_file, (old_time, old_time))

        with patch.object(mgr, '_ship_to_nas', new_callable=AsyncMock) as mock_ship, \
             patch.object(mgr, '_cleanup_nas_backups', new_callable=AsyncMock) as mock_nas_cleanup:
            mock_ship.return_value = (False, "Connection refused: 192.168.1.41 unreachable")
            success, filename, path = await mgr.create_backup()

            # Job must not crash and local backup must succeed
            assert success is True
            assert os.path.exists(path)
            # Local retention runs regardless of transfer result: old local backup is cleaned up
            assert not os.path.exists(old_file)
            # NAS retention cleanup must be skipped when transfer fails
            mock_nas_cleanup.assert_not_called()

    @pytest.mark.asyncio
    async def test_local_log_file_written(self, temp_world_dir, temp_backup_dir):
        """Verify each run logs timestamp, sizes before/after, and transfer status to local log file."""
        from src.config import config
        config.SERVER_DIR = temp_world_dir
        with open(os.path.join(temp_world_dir, "server.properties"), "w") as f:
            f.write("level-name=world\n")

        mgr = self._make_manager(temp_backup_dir, temp_world_dir)

        with patch.object(mgr, '_ship_to_nas', new_callable=AsyncMock) as mock_ship:
            mock_ship.return_value = (True, "")
            success, filename, path = await mgr.create_backup()

        assert os.path.exists(mgr.log_file)
        with open(mgr.log_file, "r") as f:
            content = f.read()

        assert filename in content
        assert "Size before:" in content
        assert "Size after:" in content
        assert "Transfer: SUCCESS" in content

    @pytest.mark.asyncio
    async def test_nas_cleanup_retention(self, temp_backup_dir):
        """Verify NAS cleanup deletes backups older than 30 days cutoff."""
        mgr = self._make_manager(temp_backup_dir, "/fake")

        remote_listing = "\n".join([
            "backup_auto_2026-10-01_03-00.tar.zst",  # 1 day old
            "backup_auto_2026-08-01_03-00.tar.zst",  # 62 days old (cutoff is 30)
            "notes.txt"
        ])

        mock_list_proc = AsyncMock()
        mock_list_proc.returncode = 0
        mock_list_proc.communicate.return_value = (remote_listing.encode(), b"")

        mock_rm_proc = AsyncMock()
        mock_rm_proc.returncode = 0
        mock_rm_proc.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = [mock_list_proc, mock_rm_proc]
            await mgr._cleanup_nas_backups(cutoff_days=30)

            assert mock_exec.call_count == 2
            rm_call = mock_exec.call_args_list[1]
            assert "rm -f '/pool-bulk/backups/mc-bot/backup_auto_2026-08-01_03-00.tar.zst'" in " ".join(rm_call[0])

