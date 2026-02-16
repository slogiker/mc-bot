"""
Version Fetcher - Dynamically fetch and cache Minecraft server versions
"""
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from src.logger import logger

class VersionFetcher:
    """Fetches and caches Minecraft server versions from various APIs"""
    
    # API endpoints
    PAPER_API = "https://api.papermc.io/v2/projects/paper"
    VANILLA_API = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    FABRIC_API = "https://meta.fabricmc.net/v2/versions/game"
    
    def __init__(self):
        self._cache = {}  # {platform: {'versions': [...], 'timestamp': datetime}}
        self._cache_duration = timedelta(hours=1)  # Cache for 1 hour
        self._lock = asyncio.Lock()  # Prevent concurrent fetches
    
    async def get_versions(self, platform: str, limit: int = 5) -> List[str]:
        """
        Get available versions for a platform
        Returns: List of version strings, latest first
        """
        async with self._lock:
            # Check cache
            if platform in self._cache:
                cache_data = self._cache[platform]
                if datetime.now() - cache_data['timestamp'] < self._cache_duration:
                    versions = cache_data['versions']
                    # Return limited versions
                    return versions[:limit] if limit else versions
            
            # Fetch from API
            try:
                versions = await self._fetch_versions(platform)
                
                # Cache the results
                self._cache[platform] = {
                    'versions': versions,
                    'timestamp': datetime.now()
                }
                
                # Return limited versions
                return versions[:limit] if limit else versions
                
            except Exception as e:
                logger.error(f"Failed to fetch versions for {platform}: {e}")
                
                # Try to return cached data even if expired
                if platform in self._cache:
                    logger.warning(f"Using expired cache for {platform}")
                    return self._cache[platform]['versions'][:limit] if limit else self._cache[platform]['versions']
                
                # Fallback to hardcoded recent versions
                return self._get_fallback_versions(platform, limit)
    
    async def get_all_versions(self, platform: str) -> List[str]:
        """Get all available versions (for "More" button)"""
        async with self._lock:
            # Check cache first
            if platform in self._cache:
                cache_data = self._cache[platform]
                if datetime.now() - cache_data['timestamp'] < self._cache_duration:
                    return cache_data['versions']
            
            # Fetch fresh
            try:
                versions = await self._fetch_versions(platform)
                self._cache[platform] = {
                    'versions': versions,
                    'timestamp': datetime.now()
                }
                return versions
            except Exception as e:
                logger.error(f"Failed to fetch all versions for {platform}: {e}")
                
                # Return cached if available
                if platform in self._cache:
                    return self._cache[platform]['versions']
                
                # Fallback
                return self._get_fallback_versions(platform, None)
    
    async def _fetch_versions(self, platform: str) -> List[str]:
        """Fetch versions from API"""
        async with aiohttp.ClientSession() as session:
            if platform == "paper":
                return await self._fetch_paper_versions(session)
            elif platform == "vanilla":
                return await self._fetch_vanilla_versions(session)
            elif platform == "fabric":
                return await self._fetch_fabric_versions(session)
            else:
                return []
    
    async def _fetch_paper_versions(self, session: aiohttp.ClientSession) -> List[str]:
        """Fetch Paper versions"""
        try:
            async with session.get(self.PAPER_API) as resp:
                if resp.status != 200:
                    raise Exception(f"Paper API returned {resp.status}")
                data = await resp.json()
                versions = data.get('versions', [])
                # Return in reverse order (latest first)
                return list(reversed(versions))
        except Exception as e:
            logger.error(f"Paper version fetch error: {e}")
            raise
    
    async def _fetch_vanilla_versions(self, session: aiohttp.ClientSession) -> List[str]:
        """Fetch Vanilla versions"""
        try:
            async with session.get(self.VANILLA_API) as resp:
                if resp.status != 200:
                    raise Exception(f"Vanilla API returned {resp.status}")
                data = await resp.json()
                versions = [v['id'] for v in data.get('versions', [])]
                # Filter to release versions only, reverse order
                release_versions = [
                    v['id'] for v in data.get('versions', [])
                    if v.get('type') == 'release'
                ]
                return list(reversed(release_versions))
        except Exception as e:
            logger.error(f"Vanilla version fetch error: {e}")
            raise
    
    async def _fetch_fabric_versions(self, session: aiohttp.ClientSession) -> List[str]:
        """Fetch Fabric versions (uses vanilla game versions)"""
        try:
            # Fabric uses vanilla game versions
            async with session.get(self.VANILLA_API) as resp:
                if resp.status != 200:
                    raise Exception(f"Vanilla API returned {resp.status}")
                data = await resp.json()
                versions = [
                    v['id'] for v in data.get('versions', [])
                    if v.get('type') == 'release'
                ]
                return list(reversed(versions))
        except Exception as e:
            logger.error(f"Fabric version fetch error: {e}")
            raise
    
    def _get_fallback_versions(self, platform: str, limit: Optional[int]) -> List[str]:
        """Fallback versions if API fails"""
        fallback = {
            "paper": ["1.21.11", "1.21.10", "1.21.9", "1.21.8", "1.21.7", "1.21.6", "1.21.5", "1.21.4", "1.20.4"],
            "vanilla": ["1.21.11", "1.21.10", "1.21.9", "1.21.8", "1.21.7", "1.21.6", "1.21.5", "1.21.4", "1.20.4"],
            "fabric": ["1.21.11", "1.21.10", "1.21.9", "1.21.8", "1.21.7", "1.21.6", "1.21.5", "1.21.4", "1.20.4"]
        }
        versions = fallback.get(platform, ["1.21.11"])
        return versions[:limit] if limit else versions
    
    async def get_latest_version(self, platform: str) -> str:
        """Get the latest version for a platform"""
        versions = await self.get_versions(platform, limit=1)
        if versions:
            return versions[0]
        # Fallback
        return "1.21.11"

# Singleton instance
version_fetcher = VersionFetcher()
