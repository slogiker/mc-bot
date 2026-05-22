import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.log_watcher import LogWatcher

@pytest.fixture
def mock_bot():
    return MagicMock()

@pytest.fixture
def log_watcher(mock_bot):
    return LogWatcher(mock_bot)

def test_check_line_vanilla(log_watcher, mock_bot):
    """Test that Vanilla/Paper log lines are correctly parsed."""
    line = "[10:22:34] [User Authenticator #1/INFO]: UUID of player slogiker is 1234abcd-5678-90ef-1234-567890abcdef"
    log_watcher._check_line(line)
    
    mock_bot.dispatch.assert_called_once_with(
        'minecraft_player_login', 
        'slogiker', 
        '1234abcd-5678-90ef-1234-567890abcdef'
    )

def test_check_line_forge(log_watcher, mock_bot):
    """Test that Forge log lines are correctly parsed."""
    line = "[10:22:34] [Netty Server IO #1/INFO]: UUID of player forge_user is 00000000-0000-0000-0000-000000000000"
    log_watcher._check_line(line)
    
    mock_bot.dispatch.assert_called_once_with(
        'minecraft_player_login', 
        'forge_user', 
        '00000000-0000-0000-0000-000000000000'
    )

def test_check_line_no_match(log_watcher, mock_bot):
    """Test that non-matching lines are ignored."""
    line = "[10:22:34] [Server thread/INFO]: slogiker joined the game"
    log_watcher._check_line(line)
    
    mock_bot.dispatch.assert_not_called()

@pytest.mark.asyncio
async def test_process_logs(log_watcher, mock_bot):
    """Test the log processing loop."""
    log_watcher._queue = asyncio.Queue()
    log_watcher._running = True
    
    # Put a line in the queue
    line = "[10:22:34] [User Authenticator #1/INFO]: UUID of player slogiker is 1234abcd-5678-90ef-1234-567890abcdef"
    await log_watcher._queue.put(line)
    
    # Run _process_logs in a task
    task = asyncio.create_task(log_watcher._process_logs())
    
    # Give it a moment to process
    await asyncio.sleep(0.1)
    
    # Stop it
    log_watcher._running = False
    # Put another line to wake up the await queue.get()
    await log_watcher._queue.put("dummy line")
    
    await asyncio.wait_for(task, timeout=1.0)

    mock_bot.dispatch.assert_called_once()
