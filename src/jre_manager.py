"""
JRE Manager - Dynamically download and manage Java Runtime Environments (JRE)
based on the required Minecraft server version.
"""
import os
import sys
import re
import platform
import shutil
import tarfile
import tempfile
import subprocess
import asyncio
from typing import Optional, Tuple
import aiohttp
import aiofiles
from src.logger import logger

class JREManager:
    """Manages downloading, caching, and running specific JRE versions"""

    def __init__(self):
        self.jre_base_dir = os.path.abspath(os.path.join("data", "jre"))
        os.makedirs(self.jre_base_dir, exist_ok=True)
        self._system_java_version: Optional[int] = None
        self._system_java_checked = False

    def get_system_java_version(self) -> Optional[int]:
        """
        Detect the major version of the system default 'java' executable.
        Returns None if java is not available or version cannot be parsed.
        """
        if self._system_java_checked:
            return self._system_java_version

        self._system_java_checked = True
        try:
            res = subprocess.run(
                ["java", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            output = res.stderr or res.stdout
            match = re.search(r'version\s+"(\d+)(?:\.(\d+))?', output)
            if match:
                g1, g2 = match.group(1), match.group(2)
                if g1 == "1" and g2:
                    self._system_java_version = int(g2)
                else:
                    self._system_java_version = int(g1)
                logger.info(f"Detected system default Java version: {self._system_java_version}")
            else:
                logger.warning(f"Could not parse Java version from output: {output[:100]}")
        except Exception as e:
            logger.debug(f"System 'java' check failed: {e}")
            self._system_java_version = None

        return self._system_java_version

    def get_required_java_version(self, mc_version: Optional[str]) -> int:
        """
        Determine the required major Java version for a given Minecraft version.
        
        Java requirements:
          - Minecraft < 1.17: Java 8
          - Minecraft 1.17 - 1.20.4: Java 17 (LTS)
          - Minecraft 1.20.5 - 1.21.x: Java 21 (LTS)
          - Minecraft 1.22+: Java 25 (LTS)
        """
        # 1. Check if user configured an explicit java_version override in config
        try:
            from src.config import config
            cfg_java = getattr(config, 'JAVA_VERSION', None)
            if cfg_java and str(cfg_java).lower() not in ('auto', 'default', 'none'):
                try:
                    return int(cfg_java)
                except ValueError:
                    pass
        except Exception:
            pass

        if not mc_version or str(mc_version).lower() in ("unknown", "none", ""):
            return 21  # Default fallback

        # Strip any platform prefix (e.g. "paper-1.20.4" -> "1.20.4", "fabric-1.21.1" -> "1.21.1")
        clean_version = re.sub(r'^[a-zA-Z_\-]+', '', str(mc_version).strip())

        parts = clean_version.split('.')
        if not parts or not parts[0]:
            return 21

        try:
            # Handle potential short version format (e.g. "26.2" or "25.3")
            if len(parts) >= 2 and not parts[0].startswith("1"):
                major = int(re.sub(r'\D', '', parts[0]))
                minor = int(re.sub(r'\D', '', parts[1]))
                if major >= 12:
                    parts = ["1", str(major), str(minor)]

            if len(parts) < 2:
                return 21

            major = int(re.sub(r'\D', '', parts[0]))
            minor = int(re.sub(r'\D', '', parts[1]))
            patch_match = re.search(r'\d+', parts[2]) if len(parts) > 2 else None
            patch = int(patch_match.group(0)) if patch_match else 0

            if major == 1:
                if minor < 17:
                    return 8
                elif minor < 20:
                    return 17
                elif minor == 20:
                    # 1.20.5+ requires Java 21
                    return 21 if patch >= 5 else 17
                elif minor == 21:
                    return 21
                else:
                    # 1.22+ requires Java 25
                    return 25
            
            return 25  # Future-proof default
        except Exception as e:
            logger.warning(f"Failed to parse Minecraft version '{mc_version}' for JRE selection: {e}. Defaulting to Java 21.")
            return 21

    def get_arch(self) -> str:
        """Get the Adoptium-compatible architecture name"""
        machine = platform.machine().lower()
        if "aarch64" in machine or "arm64" in machine:
            return "aarch64"
        elif "arm" in machine:
            return "arm"
        else:
            return "x64"

    async def ensure_jre(self, java_version: int, progress_callback=None) -> str:
        """
        Ensure the specified JRE version is downloaded and extracted.
        Returns the path to the java executable.
        """
        dest_dir = os.path.join(self.jre_base_dir, str(java_version))
        java_exe = os.path.join(dest_dir, "bin", "java")

        if os.path.exists(java_exe):
            return java_exe

        # Need to download
        arch = self.get_arch()
        url = f"https://api.adoptium.net/v3/binary/latest/{java_version}/ga/linux/{arch}/jre/hotspot/normal/eclipse"
        
        logger.info(f"Downloading JRE {java_version} ({arch}) from {url}...")
        if progress_callback:
            await progress_callback(f"📥 Downloading JRE {java_version} ({arch})...")

        temp_tar = os.path.join(self.jre_base_dir, f"jre_{java_version}.tar.gz")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        raise Exception(f"Failed to download JRE {java_version}: HTTP {resp.status}")
                    
                    total_size = int(resp.headers.get('content-length', 0))
                    downloaded = 0
                    
                    async with aiofiles.open(temp_tar, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and progress_callback:
                                percent = int((downloaded / total_size) * 100)
                                if percent % 10 == 0 or downloaded == total_size:
                                    await progress_callback(f"📥 Downloading JRE {java_version} ({percent}%)...")

            # Extract JRE
            logger.info(f"Extracting JRE {java_version} to {dest_dir}...")
            if progress_callback:
                await progress_callback(f"📦 Extracting JRE {java_version}...")

            await asyncio.to_thread(self._extract_tar, temp_tar, dest_dir)
            
            # Verify
            if os.path.exists(java_exe):
                # Set executable permissions
                os.chmod(java_exe, 0o755)
                logger.info(f"JRE {java_version} successfully installed at {dest_dir}")
                return java_exe
            else:
                raise Exception("Java executable not found after extraction")

        except Exception as e:
            logger.error(f"Failed to install JRE {java_version}: {e}", exc_info=True)
            # Cleanup broken extraction
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir, ignore_errors=True)
            raise
        finally:
            # Cleanup temp file
            if os.path.exists(temp_tar):
                try:
                    os.unlink(temp_tar)
                except Exception:
                    pass

    def _extract_tar(self, tar_path: str, dest_dir: str):
        """Extract tar.gz and flatten the top-level directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            kwargs = {}
            if hasattr(tarfile, 'data_filter'):
                kwargs['filter'] = 'data'
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=tmpdir, **kwargs)
            
            # Find the inner directory
            inner_dirs = [d for d in os.listdir(tmpdir) if os.path.isdir(os.path.join(tmpdir, d))]
            if not inner_dirs:
                raise Exception("No directory found in JRE archive")
            
            inner_dir = os.path.join(tmpdir, inner_dirs[0])
            os.makedirs(dest_dir, exist_ok=True)
            
            # Move all contents to dest_dir
            for item in os.listdir(inner_dir):
                shutil.move(os.path.join(inner_dir, item), os.path.join(dest_dir, item))

    async def get_java_executable(self, mc_version: Optional[str], progress_callback=None) -> str:
        """
        Get the path to the correct java executable for the given Minecraft version.
        Checks custom path, system java compatibility, local cache, and downloads on demand.
        """
        try:
            from src.config import config
            custom_path = getattr(config, 'JAVA_PATH', 'java')
            if custom_path != "java" and os.path.exists(custom_path):
                return custom_path
        except Exception:
            pass

        try:
            required_java = self.get_required_java_version(mc_version)
            
            # Check if system default java satisfies the requirement
            sys_java = self.get_system_java_version()
            if sys_java == required_java:
                return "java"

            # Check if JRE is already cached in data/jre/<required_java>/bin/java
            dest_dir = os.path.join(self.jre_base_dir, str(required_java))
            java_exe = os.path.join(dest_dir, "bin", "java")
            if os.path.exists(java_exe):
                return java_exe
            
            # Download on demand
            return await self.ensure_jre(required_java, progress_callback=progress_callback)
        except Exception as e:
            logger.warning(f"Failed to resolve JRE for Minecraft version '{mc_version}': {e}. Falling back to system 'java'.")
            return "java"

    async def upgrade_java_if_needed(
        self,
        new_mc_version: str,
        old_mc_version: Optional[str] = None,
        progress_callback=None
    ) -> Tuple[int, bool, str]:
        """
        Check if updating Minecraft version requires a Java runtime upgrade.
        If required, downloads and prepares the target JRE.
        
        Returns:
            Tuple of (target_java_version, was_upgraded_or_changed, java_executable_path)
        """
        new_java = self.get_required_java_version(new_mc_version)
        old_java = self.get_required_java_version(old_mc_version) if old_mc_version else (self.get_system_java_version() or 21)
        
        changed = (new_java != old_java)
        if changed:
            logger.info(f"Java version transition detected for Minecraft {new_mc_version}: Java {old_java} -> Java {new_java}")
            if progress_callback:
                await progress_callback(f"☕ Updating Java runtime from Java {old_java} to Java {new_java} (required for Minecraft {new_mc_version})...")

        java_exe = await self.get_java_executable(new_mc_version, progress_callback=progress_callback)
        return new_java, changed, java_exe

jre_manager = JREManager()
