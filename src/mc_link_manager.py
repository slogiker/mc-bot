import json
import os
import asyncio
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────────────────────
# Schema per record (keyed by str(discord_id)):
# {
#     "mc_username":     str,   — exact username, case-preserved
#     "is_premium":      bool,  — True = Mojang API confirmed real account
#     "linked_at":       str,   — ISO-8601 UTC timestamp
#     "last_verified":   float | null,  — unix timestamp of last successful /verify
#     "last_disconnect": float | null,  — unix timestamp of last MC disconnect
# }
# ──────────────────────────────────────────────────────────────────────────────

GRACE_SECONDS   = 30 * 60   # 30 minutes — how long after /verify the player can rejoin freely
LINKS_PATH      = "data/mc_links.json"
LOCK_PATH       = "data/mc_links.json.lock"


class MCLinkManager:
    def __init__(self, data_file: str = LINKS_PATH):
        self.data_file = data_file
        self.lock = asyncio.Lock()
        self._ensure_file()

    # ── File helpers ──────────────────────────────────────────────────────────

    def _ensure_file(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w") as f:
                json.dump({}, f)

    def _read_sync(self) -> dict:
        try:
            with open(self.data_file, "r") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except FileNotFoundError:
            return {}

    def _write_sync(self, data: dict):
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=4)

    async def _read(self) -> dict:
        async with self.lock:
            return await asyncio.to_thread(self._read_sync)

    async def _write(self, data: dict):
        async with self.lock:
            await asyncio.to_thread(self._write_sync, data)

    # ── Read helpers ──────────────────────────────────────────────────────────

    async def get_link_by_discord(self, discord_id: int) -> dict | None:
        """Return entry for a Discord ID, or None."""
        data = await self._read()
        return data.get(str(discord_id))

    async def get_link_by_mc(self, mc_username: str) -> dict | None:
        """Return entry (including discord_id key) for an MC username. Case-insensitive."""
        data = await self._read()
        for d_id, entry in data.items():
            if entry["mc_username"].lower() == mc_username.lower():
                return {"discord_id": int(d_id), **entry}
        return None

    # ── Write helpers ─────────────────────────────────────────────────────────

    async def link_account(self, discord_id: int, mc_username: str, is_premium: bool = False):
        """
        Link a Discord account to a Minecraft username.
        If another Discord account already owns this MC username, that link is removed first.
        Entire read-modify-write is held under one lock to prevent race conditions.
        """
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)

            # Remove any existing link for this MC username (username theft prevention)
            data = {
                k: v for k, v in data.items()
                if v["mc_username"].lower() != mc_username.lower()
            }

            data[str(discord_id)] = {
                "mc_username":     mc_username,
                "is_premium":      is_premium,
                "linked_at":       datetime.now(timezone.utc).isoformat(),
                "last_verified":   None,
                "last_disconnect": None,
            }

            await asyncio.to_thread(self._write_sync, data)

    async def unlink_account(self, discord_id: int) -> bool:
        """Remove link. Returns True if something was removed."""
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)
            if str(discord_id) not in data:
                return False
            del data[str(discord_id)]
            await asyncio.to_thread(self._write_sync, data)
            return True

    # ── Session state ─────────────────────────────────────────────────────────

    async def record_verified(self, mc_username: str):
        """
        Called when /verify succeeds.
        Sets last_verified = now, opening the 30-minute grace window.
        """
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)
            import time
            for entry in data.values():
                if entry["mc_username"].lower() == mc_username.lower():
                    entry["last_verified"] = time.time()
                    break
            await asyncio.to_thread(self._write_sync, data)

    async def record_disconnect(self, mc_username: str):
        """
        Called when a player leaves or gets collision-kicked.
        Sets last_disconnect = now. Does NOT reset grace window.
        """
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)
            import time
            for entry in data.values():
                if entry["mc_username"].lower() == mc_username.lower():
                    entry["last_disconnect"] = time.time()
                    break
            await asyncio.to_thread(self._write_sync, data)

    async def grant_emergency_grace(self, mc_username: str):
        """
        Called on collision — the real player was kicked unfairly by an impersonator.
        Sets last_verified = now so they can reconnect immediately without /verify.
        """
        await self.record_verified(mc_username)

    async def is_within_grace(self, mc_username: str) -> bool:
        """
        Returns True if the player successfully verified within the last GRACE_SECONDS (30 min).
        Grace window is based on last_verified, NOT last_disconnect.
        """
        import time
        data = await self._read()
        for entry in data.values():
            if entry["mc_username"].lower() == mc_username.lower():
                lv = entry.get("last_verified")
                if lv is None:
                    return False
                return (time.time() - lv) <= GRACE_SECONDS
        return False
