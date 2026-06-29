import os
import json
from collections import deque
import aiohttp
import aiofiles
from src.config import config
from src.logger import logger
from src.version_fetcher import version_fetcher

class MinecraftInstaller:
    """Handles downloading and installing Minecraft servers"""
    
    # API endpoints
    PAPER_API = "https://api.papermc.io/v2/projects/paper"
    VANILLA_API = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    FABRIC_API = "https://meta.fabricmc.net/v2/versions/loader"
    
    # Timeout for all API requests (prevents hanging if API is down)
    API_TIMEOUT = aiohttp.ClientTimeout(total=30)
    
    def __init__(self):
        self.server_dir = config.SERVER_DIR
        os.makedirs(self.server_dir, exist_ok=True)
    
    async def get_latest_version(self, platform: str) -> str:
        """
        Fetch the latest Minecraft version for the specified platform.
        Uses VersionFetcher to get fresh results.
        
        Args:
            platform (str): 'paper', 'vanilla', 'fabric', or 'forge'.
            
        Returns:
            str: The version string (e.g. "26.1.2"). Defaults to "26.1.2" on error.
        """
        if platform == "forge":
            return "1.20.1" # Forge still manual
            
        try:
            return await version_fetcher.get_latest_version(platform, force_fresh=True)
        except Exception as e:
            logger.error(f"Failed to fetch latest version for {platform}: {e}")
            return "26.1.2" # Safe current default
    
    async def download_server(self, platform: str, version: str, progress_callback=None) -> tuple[bool, str]:
        """
        Download the server JAR file for the given platform and version.
        
        Args:
            platform (str): The server software type.
            version (str): The specific version (e.g. "1.20.4").
            progress_callback (func, optional): Async function to receive status strings.
            
        Returns:
            tuple[bool, str]: (Success, Message/Error Path)
        """
        try:
            jar_path = os.path.join(self.server_dir, "server.jar")
            logger.info(f"Downloading {platform} server version {version} to {jar_path}")
            
            if platform == "paper":
                success, msg = await self._download_paper(version, jar_path, progress_callback)
            elif platform == "vanilla":
                success, msg = await self._download_vanilla(version, jar_path, progress_callback)
            elif platform == "fabric":
                success, msg = await self._download_fabric(version, jar_path, progress_callback)
            elif platform == "forge":
                success, msg = await self._download_forge(version, jar_path, progress_callback)
            else:
                return False, f"Unknown platform: {platform}"

            if success:
                logger.info(f"Successfully downloaded {platform} server.")
                # Pre-download the correct JRE for this Minecraft version
                try:
                    from src.jre_manager import jre_manager
                    java_version = jre_manager.get_required_java_version(version)
                    await jre_manager.ensure_jre(java_version, progress_callback)
                except Exception as jre_err:
                    logger.warning(f"Failed to pre-download JRE for version {version}: {jre_err}. Will retry on startup.")
            else:
                logger.error(f"Failed to download {platform} server: {msg}")
            
            return success, msg
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False, str(e)
    
    async def install_mod_with_dependencies(self, slug: str, game_version: str, loader: str, callback=None) -> bool:
        """
        Recursively install a mod and its required dependencies using Modrinth API.
        """
        queue = deque([slug])
        processed = set()
        success_count = 0
        
        async with aiohttp.ClientSession(timeout=self.API_TIMEOUT) as session:
            while queue:
                current_slug = queue.popleft()
                if current_slug in processed:
                    continue
                
                processed.add(current_slug)
                
                if callback:
                    await callback(f"🔍 Resolving `{current_slug}`...")
                
                # 1. Get version info
                api_url = f"https://api.modrinth.com/v2/project/{current_slug}/version"
                params = {
                    "loaders": f'["{loader}"]',
                    "game_versions": f'["{game_version}"]'
                }
                
                try:
                    async with session.get(api_url, params=params) as resp:
                        if resp.status != 200:
                            logger.warning(f"Failed to fetch versions for {current_slug}: HTTP {resp.status}")
                            continue
                        
                        versions = await resp.json()
                        if not versions:
                            logger.warning(f"No compatible versions for {current_slug} on {game_version} ({loader})")
                            continue
                        
                        # Use latest release (or latest if no release)
                        latest = versions[0]
                        for v in versions:
                            if v.get("version_type") == "release":
                                latest = v
                                break
                        
                        # 2. Check dependencies
                        for dep in latest.get("dependencies", []):
                            if dep.get("dependency_type") == "required":
                                dep_id = dep.get("project_id") or dep.get("version_id")
                                if dep_id and dep_id not in processed:
                                    queue.append(dep_id)
                        
                        # 3. Download file
                        files = latest.get("files", [])
                        primary_file = next((f for f in files if f.get("primary")), files[0] if files else None)
                        
                        if primary_file:
                            dest_dir = os.path.join(self.server_dir, "plugins" if loader == "paper" else "mods")
                            os.makedirs(dest_dir, exist_ok=True)
                            
                            file_path = os.path.join(dest_dir, primary_file["filename"])
                            
                            if os.path.exists(file_path):
                                logger.info(f"Mod {primary_file['filename']} already exists, skipping download.")
                                success_count += 1
                                continue

                            async with session.get(primary_file["url"]) as mod_resp:
                                if mod_resp.status == 200:
                                    async with aiofiles.open(file_path, 'wb') as f:
                                        async for chunk in mod_resp.content.iter_chunked(8192):
                                            await f.write(chunk)
                                    logger.info(f"Successfully downloaded: {primary_file['filename']}")
                                    if callback:
                                        await callback(f"✅ Downloaded `{primary_file['filename']}`")
                                    success_count += 1
                except Exception as e:
                    logger.error(f"Error processing mod {current_slug}: {e}")
                    continue
        
        return success_count > 0

    async def _download_paper(self, version: str, jar_path: str, callback) -> tuple[bool, str]:
        """Download Paper server"""
        try:
            async with aiohttp.ClientSession(timeout=self.API_TIMEOUT) as session:
                # Get build number
                async with session.get(f"{self.PAPER_API}/versions/{version}") as resp:
                    data = await resp.json()
                    build = data['builds'][-1]
                
                # Get download URL
                download_url = f"{self.PAPER_API}/versions/{version}/builds/{build}/downloads/paper-{version}-{build}.jar"
                
                if callback:
                    await callback(f"📥 Downloading Paper {version} (Build {build})...")
                
                # Download
                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        return False, f"Download failed: HTTP {resp.status}"
                    
                    total_size = int(resp.headers.get('content-length', 0))
                    downloaded = 0
                    
                    async with aiofiles.open(jar_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Progress update every 5MB
                            if callback and downloaded % (5 * 1024 * 1024) < 8192:
                                progress = (downloaded / total_size * 100) if total_size > 0 else 0
                                await callback(f"📥 Downloading... {progress:.1f}% ({downloaded // (1024*1024)}MB)")
                
                size_mb = os.path.getsize(jar_path) / (1024 * 1024)
                return True, f"Downloaded Paper {version} ({size_mb:.1f}MB)"
                
        except Exception as e:
            logger.error(f"Paper download failed: {e}")
            return False, str(e)
    
    async def _download_vanilla(self, version: str, jar_path: str, callback) -> tuple[bool, str]:
        """Download Vanilla server"""
        try:
            async with aiohttp.ClientSession(timeout=self.API_TIMEOUT) as session:
                # Get version manifest
                async with session.get(self.VANILLA_API) as resp:
                    manifest = await resp.json()
                
                # Find version
                version_data = None
                for v in manifest['versions']:
                    if v['id'] == version:
                        version_data = v
                        break
                
                if not version_data:
                    return False, f"Version {version} not found"
                
                # Get version details
                async with session.get(version_data['url']) as resp:
                    details = await resp.json()
                
                if 'downloads' not in details or 'server' not in details['downloads']:
                    return False, f"Mojang API does not provide a server download for version {version}. Please pick a more recent version (1.2.5+)."
                
                download_url = details['downloads']['server']['url']
                
                if callback:
                    await callback(f"📥 Downloading Vanilla {version}...")
                
                # Download
                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        return False, f"Download failed: HTTP {resp.status}"
                    
                    async with aiofiles.open(jar_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)
                
                size_mb = os.path.getsize(jar_path) / (1024 * 1024)
                return True, f"Downloaded Vanilla {version} ({size_mb:.1f}MB)"
                
        except Exception as e:
            logger.error(f"Vanilla download failed: {e}")
            return False, str(e)
    
    async def _download_fabric(self, version: str, jar_path: str, callback) -> tuple[bool, str]:
        """Download Fabric server"""
        try:
            async with aiohttp.ClientSession(timeout=self.API_TIMEOUT) as session:
                # Get latest loader
                async with session.get(f"{self.FABRIC_API}/{version}") as resp:
                    loaders = await resp.json()
                    if not loaders:
                        return False, "No Fabric loader found for this version"
                    loader_version = loaders[0]['loader']['version']
                
                # Download installer
                installer_url = f"https://meta.fabricmc.net/v2/versions/loader/{version}/{loader_version}/1.0.0/server/jar"
                
                if callback:
                    await callback(f"📥 Downloading Fabric {version}...")
                
                async with session.get(installer_url) as resp:
                    if resp.status != 200:
                        return False, f"Download failed: HTTP {resp.status}"
                    
                    async with aiofiles.open(jar_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)
                
                size_mb = os.path.getsize(jar_path) / (1024 * 1024)
                
                return True, f"Downloaded Fabric {version} ({size_mb:.1f}MB)"
                
        except Exception as e:
            logger.error(f"Fabric download failed: {e}")
            return False, str(e)
            
    async def _download_forge(self, version: str, jar_path: str, callback) -> tuple[bool, str]:
        """
        Forge automatic installation is not yet supported.
        
        For manual Forge setup, download the installer from:
          - Forge official: https://files.minecraftforge.net/
          - Modrinth API: https://api.modrinth.com/v2/ (for mods and modpacks)
          - Forge Maven: https://maven.minecraftforge.net/ (for installer JARs)
        
        Place the server JAR in the mc-server/ directory as server.jar.
        """
        return False, (
            "Forge automatic installation is not supported yet. "
            "Please download the Forge installer manually from files.minecraftforge.net "
            "or use the Modrinth API (https://api.modrinth.com/v2/) for modpack installation."
        )
    
    async def accept_eula(self) -> bool:
        """Create eula.txt with eula=true"""
        try:
            eula_path = os.path.join(self.server_dir, "eula.txt")
            async with aiofiles.open(eula_path, 'w') as f:
                await f.write("# Generated by Minecraft Discord Bot\n")
                await f.write("eula=true\n")
            logger.info("EULA accepted")
            return True
        except Exception as e:
            logger.error(f"Failed to accept EULA: {e}")
            return False
    
    async def configure_server_properties(self, settings: dict) -> bool:
        """
        Configure server.properties
        settings = {
            'difficulty': 'normal',
            'whitelist': True,
            'seed': '',
            'online_mode': False,
            'max_players': 20,
            'view_distance': 16,
            ...
        }
        """
        try:
            props_path = os.path.join(self.server_dir, "server.properties")
            
            # Default properties
            properties = {
                'enable-rcon': 'true',
                'rcon.port': '25575',
                'rcon.password': config.RCON_PASSWORD,
                'server-port': '25565',
                'difficulty': settings.get('difficulty', 'normal'),
                'white-list': 'true' if settings.get('whitelist', False) else 'false',
                'level-seed': settings.get('seed', ''),
                'online-mode': 'true' if settings.get('online_mode', True) else 'false',
                'max-players': str(settings.get('max_players', 20)),
                'view-distance': str(settings.get('view_distance', 16)),
                'motd': 'Minecraft Server - Managed by Discord Bot'
            }
            
            # Read existing properties if they exist
            if os.path.exists(props_path):
                async with aiofiles.open(props_path, 'r') as f:
                    content = await f.read()
                    for line in content.split('\n'):
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            # Only override if we have a setting for it
                            if key.strip() not in properties:
                                properties[key.strip()] = value.strip()
            
            # Write properties
            async with aiofiles.open(props_path, 'w') as f:
                await f.write("# Minecraft server properties\n")
                await f.write("# Managed by Discord Bot\n")
                for key, value in properties.items():
                    await f.write(f"{key}={value}\n")
            
            logger.info("server.properties configured")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure server.properties: {e}")
            return False
    
    async def add_to_whitelist(self, username: str) -> bool:
        """Add a player to whitelist.json"""
        # TODO: make it mascan proof
        try:
            whitelist_path = os.path.join(self.server_dir, "whitelist.json")
            props_path = os.path.join(self.server_dir, "server.properties")
            
            online_mode = True
            if os.path.exists(props_path):
                async with aiofiles.open(props_path, 'r') as f:
                    content = await f.read()
                    if "online-mode=false" in content.lower():
                        online_mode = False
            
            # Load existing whitelist
            whitelist = []
            if os.path.exists(whitelist_path):
                async with aiofiles.open(whitelist_path, 'r') as f:
                    content = await f.read()
                    whitelist = json.loads(content) if content else []
            
            if not online_mode:
                import hashlib
                import uuid
                data = f"OfflinePlayer:{username}".encode('utf-8')
                md5_hash = bytearray(hashlib.md5(data).digest())
                md5_hash[6] = (md5_hash[6] & 0x0f) | 0x30
                md5_hash[8] = (md5_hash[8] & 0x3f) | 0x80
                player_uuid = str(uuid.UUID(bytes=bytes(md5_hash)))
                
                whitelist.append({
                    "uuid": player_uuid,
                    "name": username
                })
                
                async with aiofiles.open(whitelist_path, 'w') as f:
                    await f.write(json.dumps(whitelist, indent=2))
                logger.info(f"Added {username} to offline whitelist")
                return True
            
            # Get UUID from Mojang API
            async with aiohttp.ClientSession(timeout=self.API_TIMEOUT) as session:
                async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        player_uuid = data['id']
                        # Format UUID with dashes
                        player_uuid = f"{player_uuid[:8]}-{player_uuid[8:12]}-{player_uuid[12:16]}-{player_uuid[16:20]}-{player_uuid[20:]}"
                        
                        # Add to whitelist
                        whitelist.append({
                            "uuid": player_uuid,
                            "name": username
                        })
                        
                        # Save
                        async with aiofiles.open(whitelist_path, 'w') as f:
                            await f.write(json.dumps(whitelist, indent=2))
                        
                        logger.info(f"Added {username} to whitelist")
                        return True
                    else:
                        logger.warning(f"Player {username} not found")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to add to whitelist: {e}")
            return False

# Singleton instance
mc_installer = MinecraftInstaller()