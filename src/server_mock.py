import asyncio
from src.server_interface import ServerInterface
from src.logger import logger

class MockServerManager(ServerInterface):
    """
    Mock implementation of ServerInterface for Simulation/Ghost Mode.
    Mimics a running server without starting any processes or touching files.
    """
    def __init__(self):
        self._running = False
        self._intentional_stop = True

    def is_running(self) -> bool:
        return self._running

    def is_intentionally_stopped(self) -> bool:
        return self._intentional_stop

    async def start(self) -> tuple[bool, str]:
        if self._running:
            return False, "Server is already running"
        
        logger.info("👻 GHOST MODE: 'Starting' server (Mock)...")
        await asyncio.sleep(2) # Fake startup delay
        
        self._running = True
        self._intentional_stop = False
        
        logger.info("👻 GHOST MODE: Server 'started' successfully")
        return True, "Server started successfully (Simulation)"

    async def stop(self) -> tuple[bool, str]:
        if not self._running:
            return False, "Server is not running"
            
        logger.info("👻 GHOST MODE: 'Stopping' server (Mock)...")
        await asyncio.sleep(1)
        
        self._running = False
        self._intentional_stop = True
        
        logger.info("👻 GHOST MODE: Server 'stopped' successfully")
        return True, "Server stopped successfully (Simulation)"

    async def restart(self) -> tuple[bool, str]:
        logger.info("👻 GHOST MODE: 'Restarting' server (Mock)...")
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()

    def send_command(self, cmd: str):
        if not self._running:
            logger.warning("👻 GHOST MODE: Cannot send command, server offline")
            return
        logger.info(f"👻 GHOST MODE: Sent command: '{cmd}'")
