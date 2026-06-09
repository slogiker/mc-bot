"""
Shared pytest fixtures for mc-bot tests.
"""
import os
import sys
import json
import pytest
import tempfile
import shutil

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def valid_user_config():
    """A fully valid user_config dictionary."""
    return {
        "java_ram_min": "2G",
        "java_ram_max": "4G",
        "backup_time": "03:00",
        "backup_keep_days": 7,
        "restart_time": "04:00",
        "timezone": "UTC",
        "permissions": {
            "Owner": ["start", "stop", "restart"],
            "@everyone": ["status", "help"]
        }
    }


@pytest.fixture
def temp_world_dir():
    """Create a temporary world directory with fake files for backup tests."""
    tmpdir = tempfile.mkdtemp()
    world = os.path.join(tmpdir, "world")
    os.makedirs(world)

    # Create some fake world files
    for name in ["level.dat", "level.dat_old", "session.lock"]:
        with open(os.path.join(world, name), "w") as f:
            f.write(f"fake {name} data")

    region_dir = os.path.join(world, "region")
    os.makedirs(region_dir)
    with open(os.path.join(region_dir, "r.0.0.mca"), "wb") as f:
        f.write(b"\x00" * 1024)

    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_backup_dir():
    """Create a temporary backup directory."""
    tmpdir = tempfile.mkdtemp()
    auto_dir = os.path.join(tmpdir, "auto")
    custom_dir = os.path.join(tmpdir, "custom")
    os.makedirs(auto_dir)
    os.makedirs(custom_dir)
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mock_server_log(tmp_path):
    """Create a mock server log with a version line."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "latest.log"
    log_file.write_text(
        "[12:00:00] [Server thread/INFO]: Starting minecraft server version 1.21.4\n"
        "[12:00:01] [Server thread/INFO]: Loading properties\n"
    )
    return tmp_path
