import os
import subprocess
import pytest
import getpass

def test_playit_binaries_exist():
    """Verify that the playit binary is installed."""
    binary = "playit"
    path = f"/usr/local/bin/{binary}"
    assert os.path.exists(path), f"Binary {binary} not found at {path}"
    assert os.access(path, os.X_OK), f"Binary {binary} at {path} is not executable"

def test_playit_version():
    """Verify that the playit binary executes."""
    try:
        # Since this build of playit-agent doesn't seem to have a --version flag,
        # we just verify that it runs and returns the help text.
        result = subprocess.run(["/usr/local/bin/playit", "--help"], 
                               capture_output=True, text=True, check=True)
        assert "Usage: playit" in result.stdout
    except subprocess.CalledProcessError:
        pytest.fail("Failed to execute playit binary")

def test_running_as_non_root():
    """Verify that the tests are running as the 'bot' user, not root."""
    username = getpass.getuser()
    assert username == "bot", f"Expected to be running as 'bot' user, but running as '{username}'"
    assert os.getuid() != 0, "Running as root user, which is not allowed for security"

def test_directory_permissions():
    """Verify that the bot user has write access to the required directories."""
    required_dirs = [
        "/app/mc-server",
        "/app/backups",
        "/app/logs",
        "/app/data"
    ]
    
    for d in required_dirs:
        assert os.path.exists(d), f"Directory {d} does not exist"
        assert os.access(d, os.W_OK), f"Bot user does not have write access to {d}"
        
        # Try creating a test file
        test_file = os.path.join(d, ".test_write")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            pytest.fail(f"Failed to write to {d}: {e}")

def test_config_files_exist_and_writable():
    """Verify that config files are in the data directory and writable."""
    config_files = [
        "/app/data/user_config.json",
        "/app/data/bot_config.json"
    ]
    
    # Note: These might not exist yet if the bot hasn't run, 
    # but in our Dockerfile.test we don't run the bot, we just run pytest.
    # However, src/config.py creates them on import if they don't exist.
    
    from src.config import config as bot_config
    
    for f in config_files:
        assert os.path.exists(f), f"Config file {f} should have been created"
        assert os.access(f, os.W_OK), f"Bot user should have write access to {f}"
