import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs.management import Management
from src.server_interface import ServerInterface

class MockServer(ServerInterface):
    def __init__(self):
        self._running = False
        self._intentional_stop = True
        self.start_calls = 0
        self.start_should_fail = False

    def is_running(self) -> bool:
        return self._running

    def is_intentionally_stopped(self) -> bool:
        return self._intentional_stop

    async def start(self) -> tuple[bool, str]:
        self.start_calls += 1
        if self.start_should_fail:
            # self._intentional_stop = True  <-- REMOVED as per fix
            return False, "Crashed immediately"
        
        self._intentional_stop = False
        self._running = True # Simulate it started
        return True, "Started"

    async def stop(self) -> tuple[bool, str]:
        self._running = False
        self._intentional_stop = True
        return True, "Stopped"

    async def emergency_stop(self) -> tuple[bool, str]:
        self._running = False
        self._intentional_stop = True
        return True, "Killed"

    async def restart(self) -> tuple[bool, str]:
        await self.stop()
        return await self.start()

    def send_command(self, cmd: str):
        pass

@pytest.mark.asyncio
async def test_auto_restart_loop_logic():
    bot = MagicMock()
    bot.server = MockServer()
    
    # Mock dependencies
    with patch('cogs.management.send_debug', new_callable=AsyncMock), \
         patch('cogs.management.log_dispatcher.wait_for_pattern', new_callable=AsyncMock) as mock_wait, \
         patch('cogs.management.config') as mock_config:

        mock_wait.return_value = True
        mock_config.MAX_AUTO_RESTARTS = 3
        mock_config.STARTUP_TIMEOUT = 300
        mock_config.COMMAND_CHANNEL_ID = "123"
        mock_config.DEBUG_CHANNEL_ID = "456"
        mock_config.OWNER_ID = "789"
        mock_config.SERVER_DIR = "/tmp"
        cog = Management(bot)
        cog.auto_restart_loop.stop()
        
        # Scenario 1: Server is running, nothing happens
        bot.server._running = True
        bot.server._intentional_stop = False
        await cog.auto_restart_loop()
        assert bot.server.start_calls == 0
        assert cog.consecutive_restarts == 0
        
        # Scenario 2: Server is intentionally stopped, nothing happens
        bot.server._running = False
        bot.server._intentional_stop = True
        await cog.auto_restart_loop()
        assert bot.server.start_calls == 0
        assert cog.consecutive_restarts == 0
        
        # Scenario 3: Server crashed (not running, not intentional)
        bot.server._running = False
        bot.server._intentional_stop = False
        
        # First crash
        await cog.auto_restart_loop()
        assert bot.server.start_calls == 1
        assert cog.consecutive_restarts == 1
        
        # Simulate it crashed again before next loop
        bot.server._running = False
        await cog.auto_restart_loop()
        assert bot.server.start_calls == 2
        assert cog.consecutive_restarts == 2
        
        # Third crash
        bot.server._running = False
        await cog.auto_restart_loop()
        assert bot.server.start_calls == 3
        assert cog.consecutive_restarts == 3
        
        # Fourth crash - should NOT start again (limit is 3)
        bot.server._running = False
        # Management.py says: if self.consecutive_restarts > 3: return
        # So it will increment to 4, then return.
        await cog.auto_restart_loop()
        assert bot.server.start_calls == 3 # Still 3
        assert cog.consecutive_restarts == 4
        
        # Scenario 4: Immediate crash bug (FIXED)
        cog.consecutive_restarts = 0
        bot.server.start_calls = 0
        bot.server._running = False
        bot.server._intentional_stop = False
        bot.server.start_should_fail = True 
        # In our MockServer, we still have the old behavior of setting intentional_stop = True
        # if start_should_fail is True. Let's update MockServer to match the fix.

@pytest.mark.asyncio
async def test_timeout_behavior():
    bot = MagicMock()
    bot.server = MockServer()
    
    with patch('cogs.management.send_debug', new_callable=AsyncMock), \
         patch('cogs.management.log_dispatcher.wait_for_pattern', new_callable=AsyncMock) as mock_wait, \
         patch('cogs.management.config') as mock_config:
        
        mock_wait.return_value = False # Timeout!
        mock_config.MAX_AUTO_RESTARTS = 3
        mock_config.STARTUP_TIMEOUT = 300
        mock_config.COMMAND_CHANNEL_ID = "123"
        
        cog = Management(bot)
        cog.auto_restart_loop.stop()
        
        bot.server._running = False
        bot.server._intentional_stop = False
        
        await cog.auto_restart_loop()
        assert bot.server.start_calls == 1
        assert cog.consecutive_restarts == 1
        # It timed out, but it doesn't do anything special other than logging.
        # Next loop will see it's still not running (if it failed to boot) or running (if it eventually booted).

if __name__ == "__main__":
    asyncio.run(test_auto_restart_loop_logic())
    asyncio.run(test_timeout_behavior())
