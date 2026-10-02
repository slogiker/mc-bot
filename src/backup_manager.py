import os
import asyncio
import tarfile
import subprocess
import shutil
import re
from datetime import datetime
from src.config import config
from src.logger import logger

class BackupManager:
    def __init__(self):
        # Resolve backup dir relative to the project root properly
        self.backup_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backups'))
        self.auto_dir = os.path.join(self.backup_dir, 'auto')
        self.custom_dir = os.path.join(self.backup_dir, 'custom')
        self.logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
        self.log_file = os.path.join(self.logs_dir, 'backup.log')
        
        # Remote NAS configuration
        self.nas_user = "slogiker"
        self.nas_host = "192.168.1.41"
        self.nas_dest_dir = "/pool-bulk/backups/mc-bot/"
        self.ssh_key = "~/.ssh/mc-bot-backup"
        self.local_retention_days = 7
        self.nas_retention_days = 30
        
        # Sync initialization is OK here (happens once at startup)
        os.makedirs(self.auto_dir, exist_ok=True)
        os.makedirs(self.custom_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    @property
    def _lock(self):
        if not hasattr(self, '_lazy_lock'):
            self._lazy_lock = asyncio.Lock()
        return self._lazy_lock

    async def create_backup(self, custom_name=None, server=None):
        """
        Creates a backup asynchronously.
        - Custom: If a name is provided, it is stored in 'backups/custom/' and never auto-deleted.
        - Auto: If no name, it is stored in 'backups/auto/' and subject to retention policy.
        """
        async with self._lock:
            from src.utils import get_now
            timestamp = get_now().strftime('%Y-%m-%d_%H-%M')
            
            if custom_name:
                filename = f"backup_custom_{timestamp}_{custom_name}.tar.zst"
                dest_dir = self.custom_dir
            else:
                filename = f"backup_auto_{timestamp}.tar.zst"
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

                # Run blocking archive and compression operation in a separate thread
                size_before, size_after = await asyncio.to_thread(self._archive_and_compress_world, dest_path)
                logger.info(f"Backup created successfully: {dest_path} (before: {size_before} B, after: {size_after} B)")
                
                # Ship a copy to the NAS via rsync over SSH
                transfer_success, transfer_err = await self._ship_to_nas(dest_path)
                
                # Log run to local log file
                run_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                await asyncio.to_thread(
                    self._log_run,
                    run_timestamp,
                    filename,
                    size_before,
                    size_after,
                    transfer_success,
                    transfer_err
                )
                
                # Local retention: runs every backup cycle for auto backups
                if not custom_name:
                    await self._cleanup_local_backups()

                # NAS retention: gated on successful transfer for this cycle
                if transfer_success:
                    if not custom_name:
                        await self._cleanup_nas_backups()
                else:
                    logger.warning(
                        f"Remote shipping failed: {transfer_err}. "
                        "NAS retention cleanup skipped for this cycle."
                    )
                    
                return True, filename, dest_path
            except Exception as e:
                logger.error(f"Backup failed: {e}")
                return False, str(e), None
            finally:
                if save_disabled:
                    from src.utils import rcon_cmd
                    logger.info("Re-enabling auto-save after backup.")
                    _, _ = await rcon_cmd("save-on")

    def _archive_and_compress_world(self, dest_path):
        """
        Archives the world folder to tar and compresses with zstd -19.
        Returns (size_before, size_after) in bytes.
        """
        world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
        
        if not os.path.isdir(world_path):
            raise FileNotFoundError(f"World directory not found: {world_path}")
            
        temp_tar_path = dest_path + ".tmp.tar"
        try:
            # Create uncompressed tar archive
            with tarfile.open(temp_tar_path, 'w') as tf:
                for root, dirs, files in os.walk(world_path):
                    for file in files:
                        # Skip session.lock to avoid errors if server is running
                        if file == 'session.lock':
                            continue
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, world_path)
                        tf.add(file_path, arcname=arcname)
                        
            size_before = os.path.getsize(temp_tar_path)
            
            # Compress using zstd -19 (prefer CLI, fallback to python zstandard)
            if shutil.which("zstd"):
                proc = subprocess.run(
                    ["zstd", "-19", "-q", "-f", temp_tar_path, "-o", dest_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"zstd compression failed: {proc.stderr.strip()}")
            else:
                try:
                    import zstandard
                    cctx = zstandard.ZstdCompressor(level=19)
                    with open(temp_tar_path, "rb") as f_in, open(dest_path, "wb") as f_out:
                        cctx.copy_stream(f_in, f_out)
                except ImportError:
                    raise RuntimeError("Neither 'zstd' binary nor 'zstandard' python module is available.")
                    
            size_after = os.path.getsize(dest_path)
            return size_before, size_after
        finally:
            if os.path.exists(temp_tar_path):
                try:
                    os.remove(temp_tar_path)
                except OSError:
                    pass

    def _zip_world(self, dest_path):
        """Deprecated legacy method kept for backward compatibility."""
        return self._archive_and_compress_world(dest_path)

    async def _ship_to_nas(self, local_archive_path: str) -> tuple[bool, str]:
        """
        Ships a local backup archive to the NAS via rsync over SSH.
        Returns (success, error_message).
        """
        cmd = [
            "rsync",
            "-avz",
            "-e",
            f"ssh -i {self.ssh_key}",
            local_archive_path,
            f"{self.nas_user}@{self.nas_host}:{self.nas_dest_dir}"
        ]
        logger.info(f"Shipping backup to NAS: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            if proc.returncode == 0:
                logger.info("Backup successfully shipped to NAS.")
                return True, ""
            else:
                err = stderr.decode().strip() or f"rsync exited with code {proc.returncode}"
                logger.warning(f"Failed to ship backup to NAS: {err}")
                return False, err
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            msg = "rsync transfer timed out after 300 seconds"
            logger.warning(msg)
            return False, msg
        except Exception as e:
            logger.warning(f"Error while shipping backup to NAS: {e}")
            return False, str(e)

    def _log_run(self, timestamp: str, filename: str, size_before: int, size_after: int, transfer_success: bool, error_msg: str = ""):
        """Logs backup run details to local backup log file."""
        try:
            status = "SUCCESS" if transfer_success else f"FAILURE ({error_msg})"
            log_line = (
                f"[{timestamp}] Archive: {filename} | "
                f"Size before: {size_before} bytes | "
                f"Size after: {size_after} bytes | "
                f"Transfer: {status}\n"
            )
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            logger.error(f"Failed to write to backup log file {self.log_file}: {e}")

    async def _cleanup_local_backups(self, cutoff_days=None):
        """Deletes local auto backups older than cutoff days."""
        if cutoff_days is None:
            cutoff_days = getattr(config, 'BACKUP_RETENTION_DAYS', self.local_retention_days)
        now = datetime.now()
        logger.info(f"Running local backup cleanup (cutoff: {cutoff_days} days)...")
        try:
            files = await asyncio.to_thread(os.listdir, self.auto_dir)
            for fname in files:
                if not (fname.endswith('.tar.zst') or fname.endswith('.zip')):
                    continue
                fpath = os.path.join(self.auto_dir, fname)
                try:
                    mtime_timestamp = await asyncio.to_thread(os.path.getmtime, fpath)
                    mtime = datetime.fromtimestamp(mtime_timestamp)
                    if (now - mtime).days > cutoff_days:
                        await asyncio.to_thread(os.remove, fpath)
                        logger.info(f"Deleted old local backup: {fname}")
                except Exception as e:
                    logger.error(f"Failed to delete old local backup {fname}: {e}")
        except Exception as e:
            logger.error(f"Failed to list local backups for cleanup: {e}")

    async def _cleanup_nas_backups(self, cutoff_days=None):
        """Deletes NAS auto backups older than cutoff days."""
        if cutoff_days is None:
            cutoff_days = self.nas_retention_days
        logger.info(f"Running NAS backup cleanup (cutoff: {cutoff_days} days)...")
        try:
            list_cmd = [
                "ssh",
                "-i",
                self.ssh_key,
                f"{self.nas_user}@{self.nas_host}",
                f"ls -1 {self.nas_dest_dir}"
            ]
            proc = await asyncio.create_subprocess_exec(
                *list_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                logger.warning(f"Failed to list NAS backups for cleanup: {stderr.decode().strip()}")
                return

            files = stdout.decode().splitlines()
            now = datetime.now()
            to_delete = []

            for fname in files:
                fname = fname.strip()
                if not (fname.startswith("backup_auto_") and (fname.endswith(".tar.zst") or fname.endswith(".zip"))):
                    continue
                date_match = re.search(r'backup_auto_(\d{4}-\d{2}-\d{2})', fname)
                if date_match:
                    try:
                        file_date = datetime.strptime(date_match.group(1), '%Y-%m-%d')
                        if (now - file_date).days > cutoff_days:
                            to_delete.append(fname)
                    except ValueError:
                        pass

            if to_delete:
                logger.info(f"Deleting {len(to_delete)} old backups from NAS...")
                remote_paths = " ".join(f"'{self.nas_dest_dir.rstrip('/')}/{f}'" for f in to_delete)
                rm_cmd = [
                    "ssh",
                    "-i",
                    self.ssh_key,
                    f"{self.nas_user}@{self.nas_host}",
                    f"rm -f {remote_paths}"
                ]
                proc_rm = await asyncio.create_subprocess_exec(
                    *rm_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL
                )
                _, stderr_rm = await asyncio.wait_for(proc_rm.communicate(), timeout=30)
                if proc_rm.returncode == 0:
                    for f in to_delete:
                        logger.info(f"Deleted old NAS backup: {f}")
                else:
                    logger.warning(f"Failed to delete old NAS backups: {stderr_rm.decode().strip()}")
        except Exception as e:
            logger.warning(f"Error during NAS backup cleanup: {e}")

    async def _cleanup_auto_backups(self):
        """Backward compatible alias for _cleanup_local_backups."""
        await self._cleanup_local_backups()

backup_manager = BackupManager()
