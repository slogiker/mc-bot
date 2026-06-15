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
async def test_tmux_server_manager_start_auto_generation():
    manager = TmuxServerManager()
    
    # Mock dependencies
    with patch('src.server_tmux.os.path.exists') as mock_exists, \
         patch('src.server_tmux.asyncio.create_subprocess_exec') as mock_create_subprocess, \
         patch('src.server_tmux.asyncio.timeout') as mock_timeout, \
         patch.object(manager, 'is_running', return_value=False), \
         patch.object(manager, '_run_tmux_cmd') as mock_run_tmux, \
         patch.object(manager, '_save_state', new_callable=AsyncMock):
         
        # Setup os.path.exists to return True for jar, False for world initially, then True for world after generation
        def exists_side_effect(path):
            if path == os.path.join(config.SERVER_DIR, config.SERVER_JAR):
                return True
            if path == os.path.join(config.SERVER_DIR, config.WORLD_FOLDER):
                # Return False the first time, True the second time
                if not hasattr(exists_side_effect, 'world_checked'):
                    exists_side_effect.world_checked = True
                    return False
                return True
            if path == config.SERVER_DIR:
                return True
            return True
            
        mock_exists.side_effect = exists_side_effect
        
        # Setup mock process
        mock_proc = MagicMock()
        mock_proc.stdout = AsyncMock()
        # Simulate reading lines: first a random line, then the "Done" line, then EOF
        mock_proc.stdout.readline.side_effect = [
            b"Starting minecraft server version 1.20.4\n",
            b"[Server thread/INFO]: Done (10.123s)! For help, type \"help\"\n",
            b""
        ]
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.drain = AsyncMock()
        mock_proc.wait = AsyncMock()
        
        mock_create_subprocess.return_value = mock_proc
        
        # Setup mock timeout context manager
        mock_timeout_ctx = MagicMock()
        mock_timeout_ctx.__aenter__ = AsyncMock()
        mock_timeout_ctx.__aexit__ = AsyncMock()
        mock_timeout.return_value = mock_timeout_ctx
        
        # Setup tmux command to succeed
        mock_run_tmux_res = MagicMock()
        mock_run_tmux_res.returncode = 0
        mock_run_tmux.return_value = mock_run_tmux_res
        
        # Run start()
        # We need to mock asyncio.sleep so it doesn't actually wait 10 seconds
        # Also mock is_running to return True after sleep so it doesn't think it crashed
        with patch('src.server_tmux.asyncio.sleep', new_callable=AsyncMock):
            with patch.object(manager, 'is_running', side_effect=[False, True]):
                success, msg = await manager.start()
            
        # Assertions
        assert success is True
        assert msg == "Server started successfully"
        
        # Verify create_subprocess_exec was called with correct arguments
        mock_create_subprocess.assert_called_once()
        args, kwargs = mock_create_subprocess.call_args
        assert args[0] == "java"
        assert "-jar" in args
        
        # Verify stop command was sent to stdin
        mock_proc.stdin.write.assert_called_with(b"stop\n")
        mock_proc.stdin.drain.assert_called_once()
        
        # Verify tmux new-session was called
        mock_run_tmux.assert_any_call(["kill-session", "-t", manager.session_name])
        
        # Find the new-session call
        new_session_called = False
        for call in mock_run_tmux.call_args_list:
            args, _ = call
            if args[0][0] == "new-session":
                new_session_called = True
                break
        assert new_session_called
