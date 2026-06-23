import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

from src.rcon_manager import RCONManager
from src.server_tmux import TmuxServerManager
from src.config import config

@pytest.mark.asyncio
async def test_rcon_manager_get_client_connection_refused():
    manager = RCONManager()
    
    # Mock the Client class from aiomcrcon
    with patch('src.rcon_manager.Client') as MockClient:
        mock_client_instance = MagicMock()
        # Make connect() raise an exception
        mock_client_instance.connect = AsyncMock(side_effect=ConnectionRefusedError("Connection refused"))
        MockClient.return_value = mock_client_instance
        
        # Call get_client and expect the exception to bubble up
        with pytest.raises(ConnectionRefusedError, match="Connection refused"):
            await manager.get_client()
            
        # Verify that _client remains None
        assert manager._client is None
        
        # Verify connect was called
        mock_client_instance.connect.assert_called_once()

@pytest.mark.asyncio
async def test_tmux_server_manager_start_crash_missing_world():
    manager = TmuxServerManager()
    
    with patch('src.server_tmux.os.path.exists') as mock_exists, \
         patch('src.server_tmux.asyncio.to_thread') as mock_to_thread, \
         patch.object(manager, 'is_running', side_effect=[False, False]), \
         patch.object(manager, '_run_tmux_cmd') as mock_run_tmux, \
         patch.object(manager, '_save_state', new_callable=AsyncMock), \
         patch('src.server_tmux.asyncio.sleep', new_callable=AsyncMock):
         
        # We need to handle asyncio.to_thread correctly by making it an AsyncMock that calls the target function
        async def mock_to_thread_impl(func, *args, **kwargs):
            return func(*args, **kwargs)
        mock_to_thread.side_effect = mock_to_thread_impl
        
        # Setup os.path.exists
        def exists_side_effect(path):
            if path == os.path.join(config.SERVER_DIR, config.SERVER_JAR):
                return True
            if path == config.SERVER_DIR:
                return True
            if path == os.path.join(config.SERVER_DIR, config.WORLD_FOLDER):
                return False
            return True
            
        mock_exists.side_effect = exists_side_effect
        
        # Setup tmux command to succeed
        mock_run_tmux_res = MagicMock()
        mock_run_tmux_res.returncode = 0
        mock_run_tmux.return_value = mock_run_tmux_res
        
        # Run start()
        success, msg = await manager.start()
            
        # Assertions
        assert success is False
        assert "Server crashed before creating the world folder" in msg
