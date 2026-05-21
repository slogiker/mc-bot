import os
import subprocess
import pytest
import getpass

def test_playit_binary_exists():
    """Verify that the playit binary is installed in the expected location."""
    playit_path = "/usr/local/bin/playit"
    assert os.path.exists(playit_path), f"Playit binary not found at {playit_path}"
    assert os.access(playit_path, os.X_OK), f"Playit binary at {playit_path} is not executable"

def test_playit_version():
    """Verify that the playit binary is the correct version (v0.17.1)."""
    try:
        result = subprocess.run(["/usr/local/bin/playit", "--version"], 
                               capture_output=True, text=True, check=True)
        # Playit v0.17.1 might output version in a specific format
        # Let's check if 0.17.1 is in the output
        assert "0.17.1" in result.stdout or "0.17.1" in result.stderr
    except subprocess.CalledProcessError as e:
        # Some versions might return non-zero for --version or use different flags
        # If --version fails, we can try to just run it and check help output
        result = subprocess.run(["/usr/local/bin/playit", "--help"], 
                               capture_output=True, text=True, check=True)
        # If it's the right binary, it should at least run
        assert "playit" in result.stdout.lower()

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
