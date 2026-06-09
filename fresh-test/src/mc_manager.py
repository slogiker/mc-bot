"""
Global Minecraft Server Manager Instance

This module provides a singleton instance of the server manager that can be
imported and used throughout the application. It automatically selects between
TmuxServerManager (real) and MockServerManager (simulation) based on the
application's configuration.

Usage:
    from src.mc_manager import mc_manager
    success, msg = await mc_manager.start()
"""

import os
from typing import Dict, Optional
from src.config import config
from src.server_interface import ServerInterface




def get_server_properties() -> Optional[Dict[str, str]]:
    """
    Read and parse the server.properties file.
    
    Returns:
        Dict[str, str]: Dictionary of server properties, or None if file doesn't exist
    """
    try:
        props_path = os.path.join(config.SERVER_DIR, "server.properties")
        
        if not os.path.exists(props_path):
            return None
        
        properties = {}
        with open(props_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    properties[key.strip()] = value.strip()
        
        return properties
        
    except Exception as e:
        from src.logger import logger
        logger.error(f"Failed to read server.properties: {e}")
        return None



