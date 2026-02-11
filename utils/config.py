import json
import os
import asyncio
from filelock import FileLock
from typing import Dict, Any

DATA_DIR = os.path.join(os.getcwd(), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

BOT_CONFIG_FILE = os.path.join(DATA_DIR, 'bot_config.json')
USER_CONFIG_FILE = os.path.join(DATA_DIR, 'user_config.json')

def load_json_locked(filepath: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
    """Load a JSON file with a file lock for thread safety."""
    if default is None:
        default = {}
    
    lock = FileLock(filepath + ".lock")
    with lock:
        if not os.path.exists(filepath):
            # Create the file with default content if it doesn't exist
            with open(filepath, 'w') as f:
                json.dump(default, f, indent=4)
            return default
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default

def save_json_locked(filepath: str, data: Dict[str, Any]):
    """Save data to a JSON file with a file lock for thread safety."""
    lock = FileLock(filepath + ".lock")
    with lock:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

def load_bot_config() -> Dict[str, Any]:
    """Load the bot configuration."""
    return load_json_locked(BOT_CONFIG_FILE, default={
        "server_path": "./mc-server",
        "rcon": {
            "host": "localhost",
            "port": 25575,
            "pass": ""
        },
        "owner_id": 0,
        "console_channel_id": None,
        "log_pos": 0,
        "mappings": {},
        "economy": {},
        "events": []
    })

def save_bot_config(data: Dict[str, Any]):
    """Save the bot configuration."""
    save_json_locked(BOT_CONFIG_FILE, data)

def load_user_config() -> Dict[str, Any]:
    """Load user preferences."""
    return load_json_locked(USER_CONFIG_FILE, default={
        "log_blacklist": [],
        "triggers": {},
        "debug_mode": False
    })

def save_user_config(data: Dict[str, Any]):
    """Save user preferences."""
    save_json_locked(USER_CONFIG_FILE, data)
