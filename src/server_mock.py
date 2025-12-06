import asyncio
from src.server_interface import ServerInterface
from src.logger import logger

class MockServerManager(ServerInterface):
    def __init__(self):
        self._running = False
        self._intentional_stop = True

    def is_running(self) -> bool:
        return self._running

    def is_intentionally_stopped(self) -> bool:
        return self._intentional_stop

    async def start(self):
        if self._running:
            logger.info("[MOCK] Server already running.")
            return False
        
        logger.info("[MOCK] Starting server...")
        await asyncio.sleep(2) # Simulate startup time
        self._running = True
        self._intentional_stop = False
        logger.info("[MOCK] Server started.")
        return True

    async def stop(self):
        if not self._running:
            logger.info("[MOCK] Server not running.")
            return False
        
        logger.info("[MOCK] Stopping server...")
        await asyncio.sleep(1)
        self._running = False
        self._intentional_stop = True
        logger.info("[MOCK] Server stopped.")
        return True

    async def restart(self):
        logger.info("[MOCK] Restarting server...")
        await self.stop()
        await asyncio.sleep(1)
        await self.start()
        return True

    def send_command(self, cmd: str):
        logger.info(f"[MOCK] Sending command to console: {cmd}")
