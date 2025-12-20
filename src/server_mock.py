import asyncio
from src.server_interface import ServerInterface
from src.logger import logger

from src.config import config
from src.utils import send_debug

class MockServerManager(ServerInterface):
    def __init__(self, bot):
        self.bot = bot
        self._running = False
        self._intentional_stop = True

    async def _log_to_discord(self, message: str):
        if not self.bot:
            return
        
        channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if channel:
            try:
                await channel.send(f"[MOCK] {message}")
            except Exception as e:
                logger.error(f"Failed to send mock log to Discord: {e}")
        else:
            logger.warning(f"Log channel {config.LOG_CHANNEL_ID} not found.")

    def is_running(self) -> bool:
        return self._running

    def is_intentionally_stopped(self) -> bool:
        return self._intentional_stop

    async def start(self):
        if self._running:
            logger.info("[MOCK] Server already running.")
            await self._log_to_discord("Server is already running.")
            return False
        
        logger.info("[MOCK] Starting server...")
        await self._log_to_discord("Starting server...")
        await asyncio.sleep(2) # Simulate startup time
        self._running = True
        self._intentional_stop = False
        logger.info("[MOCK] Server started.")
        await self._log_to_discord("Server started.")
        return True

    async def stop(self):
        if not self._running:
            logger.info("[MOCK] Server not running.")
            await self._log_to_discord("Server is not running.")
            return False
        
        logger.info("[MOCK] Stopping server...")
        await self._log_to_discord("Stopping server...")
        await asyncio.sleep(1)
        self._running = False
        self._intentional_stop = True
        logger.info("[MOCK] Server stopped.")
        await self._log_to_discord("Server stopped.")
        return True

    async def restart(self):
        logger.info("[MOCK] Restarting server...")
        await self._log_to_discord("Restarting server...")
        await self.stop()
        await asyncio.sleep(1)
        await self.start()
        return True

    def send_command(self, cmd: str):
        logger.info(f"[MOCK] Sending command to console: {cmd}")
        # Asynchronously log this, but since this is not async method, we need to create task
        self.bot.loop.create_task(self._log_to_discord(f"Executed command: `{cmd}`"))
