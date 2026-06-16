"""
Tests for remove-world CLI subcommand in bot.py
"""
import os
import shutil
import zipfile
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from src.config import Config
from bot import handle_remove_world

@pytest.fixture
def mock_dependencies():
    """Setup all standard patches to isolate handle_remove_world from system side-effects."""
    with patch("bot.send_discord_debug_message", new_callable=AsyncMock) as mock_send_debug, \
         patch("src.config.config.SERVER_DIR", "/fake/server") as mock_server_dir, \
         patch("src.config.Config.WORLD_FOLDER", new_callable=PropertyMock, return_value="world") as mock_world_folder, \
         patch("os.path.exists") as mock_exists, \
         patch("os.makedirs") as mock_makedirs, \
         patch("shutil.rmtree") as mock_rmtree, \
         patch("zipfile.ZipFile") as mock_zipfile, \
         patch("os.walk") as mock_walk, \
         patch("os.getpid", return_value=123) as mock_getpid, \
         patch("os.kill") as mock_kill:
        
        # Default behavior: world folder exists, we are not in docker (or we mock exist checks)
        mock_exists.side_effect = lambda path: path == os.path.join("/fake/server", "world")
        
        yield {
            "send_debug": mock_send_debug,
            "exists": mock_exists,
            "makedirs": mock_makedirs,
            "rmtree": mock_rmtree,
            "zipfile": mock_zipfile,
            "walk": mock_walk,
            "kill": mock_kill
        }

@pytest.mark.asyncio
@patch("builtins.input", return_value="n")
@patch("src.server_tmux.TmuxServerManager.is_running", return_value=False)
async def test_remove_world_no_backup(mock_is_running, mock_input, mock_dependencies):
    """If user responds 'n' to backup, the world should be removed without backing up."""
    await handle_remove_world()
    
    # Check that debug message was sent
    mock_dependencies["send_debug"].assert_called_once()
    assert "remove-world initiated" in mock_dependencies["send_debug"].call_args[0][0]
    
    # Check that world was removed
    mock_dependencies["rmtree"].assert_called_once_with(os.path.join("/fake/server", "world"))
    
    # Check that no zip/backup directory was created
    mock_dependencies["makedirs"].assert_not_called()
    mock_dependencies["zipfile"].assert_not_called()

@pytest.mark.asyncio
@patch("builtins.input", return_value="y")
@patch("src.server_tmux.TmuxServerManager.is_running", return_value=False)
async def test_remove_world_with_backup(mock_is_running, mock_input, mock_dependencies):
    """If user responds 'y' to backup, a zip is created and then the world is removed."""
    # Mock os.walk to return a fake file structure for zipping
    mock_dependencies["walk"].return_value = [
        ("/fake/server/world", [], ["level.dat", "session.lock"])
    ]
    
    await handle_remove_world()
    
    # Verify backup dir was created
    mock_dependencies["makedirs"].assert_called_once_with(os.path.join("backups", "removed_worlds"), exist_ok=True)
    
    # Verify ZipFile was initialized
    mock_dependencies["zipfile"].assert_called_once()
    
    # Verify world was removed
    mock_dependencies["rmtree"].assert_called_once_with(os.path.join("/fake/server", "world"))

@pytest.mark.asyncio
@patch("builtins.input", side_effect=["y", "y"])
@patch("src.server_tmux.TmuxServerManager.is_running", return_value=True)
@patch("src.server_tmux.TmuxServerManager.stop", new_callable=AsyncMock, return_value=(True, "Stopped"))
async def test_remove_world_server_running_peaceful(mock_stop, mock_is_running, mock_input, mock_dependencies):
    """If the server is running, it should be stopped peacefully before deletion."""
    mock_dependencies["walk"].return_value = []
    
    await handle_remove_world()
    
    # Verify server stop was called
    mock_stop.assert_called_once()
    
    # Verify removal still happened
    mock_dependencies["rmtree"].assert_called_once_with(os.path.join("/fake/server", "world"))

@pytest.mark.asyncio
@patch("builtins.input", return_value="n")
@patch("src.server_tmux.TmuxServerManager.is_running", return_value=False)
async def test_remove_world_docker_shutdown(mock_is_running, mock_input, mock_dependencies):
    """If in Docker and PID is not 1, we should signal PID 1 to shutdown."""
    # Make os.path.exists think we are in docker by saying /.dockerenv exists
    original_exists = mock_dependencies["exists"].side_effect
    mock_dependencies["exists"].side_effect = lambda path: True if path == "/.dockerenv" or path == os.path.join("/fake/server", "world") else original_exists(path)
    
    await handle_remove_world()
    
    # Verify kill was called with SIGTERM to PID 1
    import signal
    mock_dependencies["kill"].assert_called_once_with(1, signal.SIGTERM)
