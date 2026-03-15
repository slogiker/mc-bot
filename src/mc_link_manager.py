import json
import os
import asyncio
from datetime import datetime, timezone

class MCLinkManager:
    """
    Manages the linkage between Discord Accounts and Minecraft Usernames.
    Backing store: data/mc_links.json
    Schema:
    {
       "discord_user_id": {
           "mc_username": "player123",
           "is_premium": False,
           "linked_at": "ISO_TIMESTAMP"
       }
    }
    """
    def __init__(self, data_file="data/mc_links.json"):
        self.data_file = data_file
        self.lock = asyncio.Lock()
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists("data"):
            os.makedirs("data")
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump({}, f)

    async def _read_data(self) -> dict:
        async with self.lock:
            try:
                # To prevent blocking the main thread entirely, use to_thread
                return await asyncio.to_thread(self._read_sync)
            except Exception:
                return {}

    def _read_sync(self) -> dict:
        try:
            with open(self.data_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except FileNotFoundError:
            return {}

    async def _write_data(self, data: dict):
        async with self.lock:
            await asyncio.to_thread(self._write_sync, data)

    def _write_sync(self, data: dict):
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)

    async def link_account(self, discord_id: int, mc_username: str, is_premium: bool = False):
        """Link a Discord ID to a Minecraft username."""
        data = await self._read_data()
        
        # Remove any existing link for this MC username
        discord_id_str = str(discord_id)
        to_remove = []
        for d_id, info in data.items():
            if info["mc_username"].lower() == mc_username.lower():
                to_remove.append(d_id)
        
        for d_id in to_remove:
            del data[d_id]
            
        data[discord_id_str] = {
            "mc_username": mc_username,
            "is_premium": is_premium,
            "linked_at": datetime.now(timezone.utc).isoformat()
        }
        await self._write_data(data)

    async def unlink_account(self, discord_id: int) -> bool:
        """Unlink a Discord ID."""
        data = await self._read_data()
        discord_id_str = str(discord_id)
        if discord_id_str in data:
            del data[discord_id_str]
            await self._write_data(data)
            return True
        return False

    async def get_link_by_discord(self, discord_id: int) -> dict | None:
        """Get link info for a specific Discord ID."""
        data = await self._read_data()
        return data.get(str(discord_id))

    async def get_link_by_mc(self, mc_username: str) -> dict | None:
        """Get link info (including Discord ID) for a specific MC Username."""
        data = await self._read_data()
        for d_id, info in data.items():
            if info["mc_username"].lower() == mc_username.lower():
                return {"discord_id": int(d_id), **info}
        return None
