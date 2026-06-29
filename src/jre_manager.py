"""
JRE Manager - Dynamically download and manage Java Runtime Environments (JRE)
based on the required Minecraft server version.
"""
import os
import sys
import platform
import shutil
import tarfile
import tempfile
import aiohttp
import aiofiles
from src.logger import logger

class JREManager:
    """Manages downloading, caching, and running specific JRE versions"""

    def __init__(self):
        self.jre_base_dir = os.path.abspath(os.path.join("data", "jre"))
        os.makedirs(self.jre_base_dir, exist_ok=True)

    def get_required_java_version(self, mc_version: str) -> int:
        """
        Determine the required major Java version for a given Minecraft version.
        
        Java requirements:
          - Minecraft < 1.17: Java 8
          - Minecraft 1.17 - 1.20.4: Java 17 (LTS)
          - Minecraft 1.20.5 - 1.21.4: Java 21 (LTS)
          - Minecraft 1.22+: Java 25 (LTS)
        """
        if not mc_version or mc_version.lower() == "unknown":
            return 21  # Default fallback

        # Normalize version (e.g., "26.2" -> "1.26.2")
        parts = mc_version.split('.')
        if not parts:
            return 21

        try:
            # Handle potential short version format (e.g. "26.2" or "25.3")
            if len(parts) >= 2 and not parts[0].startswith("1"):
                major = int(parts[0])
                minor = int(parts[1])
                # If it's a version like 26.2, treat it as 1.26.2
                if major >= 12:
                    parts = ["1", str(major), str(minor)]

            if len(parts) < 2:
                return 21

            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

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
                                # Throttle callbacks slightly
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
                os.unlink(temp_tar)

    def _extract_tar(self, tar_path: str, dest_dir: str):
        """Extract tar.gz and flatten the top-level directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=tmpdir)
            
            # Find the inner directory
            inner_dirs = [d for d in os.listdir(tmpdir) if os.path.isdir(os.path.join(tmpdir, d))]
            if not inner_dirs:
                raise Exception("No directory found in JRE archive")
            
            inner_dir = os.path.join(tmpdir, inner_dirs[0])
            os.makedirs(dest_dir, exist_ok=True)
            
            # Move all contents to dest_dir
            for item in os.listdir(inner_dir):
                shutil.move(os.path.join(inner_dir, item), os.path.join(dest_dir, item))

    async def get_java_executable(self, mc_version: str) -> str:
        """Get the path to the correct java executable for the given Minecraft version"""
        if not mc_version or mc_version.lower() == "unknown":
            return "java"  # Fallback to system default

        try:
            java_version = self.get_required_java_version(mc_version)
            # Check if already installed
            dest_dir = os.path.join(self.jre_base_dir, str(java_version))
            java_exe = os.path.join(dest_dir, "bin", "java")
            if os.path.exists(java_exe):
                return java_exe
            
            # Download on demand
            return await self.ensure_jre(java_version)
        except Exception as e:
            logger.warning(f"Failed to resolve JRE for Minecraft version '{mc_version}': {e}. Falling back to system 'java'.")
            return "java"

import asyncio
jre_manager = JREManager()
