import asyncio
from aiomcrcon import Client
from src.config import config
from src.logger import logger

class RCONManager:
    """
    Manages a persistent RCON connection to the Minecraft server.
    Avoids the overhead of connecting and logging in for every single command.
    """
    def __init__(self):
        self._client = None

    @property
    def _lock(self):
        if not hasattr(self, '_lazy_lock'):
            self._lazy_lock = asyncio.Lock()
        return self._lazy_lock

    async def get_client(self) -> Client:
        """Returns a connected RCON client, reconnecting if necessary."""
        async with self._lock:
            if self._client is None:
                logger.info("RCON: Connecting to server...")
                client = Client(config.RCON_HOST, config.RCON_PORT, config.RCON_PASSWORD)
                try:
                    await client.connect()
                    self._client = client
                except Exception as e:
                    # Connection failed (server probably still starting)
                    # Don't save the broken client instance
                    raise e
            return self._client

    async def send_command(self, cmd: str) -> tuple[bool, str]:
        """Sends a command to the server and returns (success, response_string)."""
        try:
            client = await self.get_client()
            # aiomcrcon returns (response_string, request_id)
            response, _ = await client.send_cmd(cmd)
            return True, response
        except Exception as e:
            logger.warning(f"RCON command failed: {e}. Attempting reconnect...")
            # Try once with a fresh connection
            async with self._lock:
                if self._client:
                    try:
                        await self._client.close()
                    except Exception:
                        pass
                    self._client = None
            
            try:
                client = await self.get_client()
                response, _ = await client.send_cmd(cmd)
                return True, response
            except Exception as e2:
                logger.error(f"RCON reconnect failed: {e2}")
                return False, f"Error: {e2}"

    async def close(self):
        """Closes the RCON connection."""
        async with self._lock:
            if self._client:
                await self._client.close()
                self._client = None
                logger.info("RCON connection closed")

# Singleton instance
rcon_manager = RCONManager()
