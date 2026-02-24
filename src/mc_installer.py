import os
import json
import aiohttp
import asyncio
import aiofiles
from src.config import config
from src.logger import logger

class MinecraftInstaller:
    """Handles downloading and installing Minecraft servers"""
    
    # API endpoints
    PAPER_API = "https://api.papermc.io/v2/projects/paper"
    VANILLA_API = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    FABRIC_API = "https://meta.fabricmc.net/v2/versions/loader"
    
    def __init__(self):
        self.server_dir = config.SERVER_DIR
        os.makedirs(self.server_dir, exist_ok=True)
    
    async def get_latest_version(self, platform: str) -> str:
        """
        Fetch the latest Minecraft version for the specified platform.
        
        Supported Platforms:
        - paper: Fetches from PaperMC API (v2).
        - vanilla: Fetches from Mojang Launcher Meta.
        - fabric: Fetches via Fabric Meta (resolves to latest generic version).
        - forge: currently defaults to 1.20.1 (API complexity).
        
        Args:
            platform (str): 'paper', 'vanilla', 'fabric', or 'forge'.
            
        Returns:
            str: The version string (e.g. "1.21.1"). Defaults to "1.20.1" on error.
        """
        try:
            async with aiohttp.ClientSession() as session:
                if platform == "paper":
                    async with session.get(self.PAPER_API) as resp:
                        data = await resp.json()
                        return data['versions'][-1]  # Latest version
                        
                elif platform == "vanilla":
                    async with session.get(self.VANILLA_API) as resp:
                        data = await resp.json()
                        return data['latest']['release']
                        
                elif platform == "fabric":
                    async with session.get(f"{self.FABRIC_API}") as resp:
                        data = await resp.json()
                        # Get latest game version
                        async with session.get(self.VANILLA_API) as resp2:
                            vanilla_data = await resp2.json()
                            return vanilla_data['latest']['release']
                            
                elif platform == "forge":
                    # Forge API is more complex, default to 1.20.1 for now
                    # TODO: Implement dynamic Forge version fetching
                    return "1.20.1"
                    
        except Exception as e:
            logger.error(f"Failed to get latest version for {platform}: {e}")
            return "1.20.1"  # Fallback
    
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
            
            if platform == "paper":
                return await self._download_paper(version, jar_path, progress_callback)
            elif platform == "vanilla":
                return await self._download_vanilla(version, jar_path, progress_callback)
            elif platform == "fabric":
                return await self._download_fabric(version, jar_path, progress_callback)
            elif platform == "forge":
                return await self._download_forge(version, jar_path, progress_callback)
            else:
                return False, f"Unknown platform: {platform}"
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False, str(e)
    
    async def _download_paper(self, version: str, jar_path: str, callback) -> tuple[bool, str]:
        """Download Paper server"""
        try:
            async with aiohttp.ClientSession() as session:
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
            async with aiohttp.ClientSession() as session:
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
            async with aiohttp.ClientSession() as session:
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
        """Download Forge server (simplified - user should download manually for now)"""
        # TODO: Implement Forge installer download and execution (requires Java headless run)
        return False, "Forge installation requires manual download from files.minecraftforge.net"
    
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
            async with aiohttp.ClientSession() as session:
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