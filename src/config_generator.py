"""
Auto-generate config.json with intelligent defaults.

This module detects server settings automatically and creates a 
config.json file with sensible defaults, only prompting for essential values.
"""

import os
import json
import psutil
import glob
import subprocess
from pathlib import Path


class ConfigGenerator:
    """Generates config.json with intelligent defaults"""
    
    def __init__(self):
        self.config = {}
        
    def detect_server_directory(self) -> str:
        """Detect Minecraft server directory"""
        # Common locations to check
        candidates = [
            "./mc-server",
            "../mc-server",
            "./server",
            ".",
        ]
        
        for path in candidates:
            if os.path.exists(path):
                # Check if it contains a server jar
                jars = glob.glob(os.path.join(path, "*.jar"))
                if jars:
                    return os.path.abspath(path)
        
        # Default fallback
        return os.path.abspath("./mc-server")
    
    def detect_server_jar(self, server_dir: str) -> str:
        """Find server.jar in the directory"""
        # Look for common server jar patterns
        patterns = [
            "server.jar",
            "minecraft_server*.jar",
            "paper*.jar",
            "spigot*.jar",
            "fabric*.jar",
            "forge*.jar",
        ]
        
        for pattern in patterns:
            matches = glob.glob(os.path.join(server_dir, pattern))
            if matches:
                return os.path.basename(matches[0])
        
        return "server.jar"  # Default
    
    def detect_java_path(self) -> str:
        """Detect Java installation"""
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return "java"
        except Exception:
            pass
        
        # Try common Java paths on different OS
        common_paths = [
            "/usr/bin/java",
            "C:\\Program Files\\Java\\jdk-17\\bin\\java.exe",
            "C:\\Program Files\\Java\\jre\\bin\\java.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return "java"  # Default, hope it's in PATH
    
    def calculate_java_memory(self) -> tuple[str, str]:
        """Calculate optimal Java memory based on available RAM"""
        try:
            total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
            
            # Conservative allocation strategy
            if total_ram_gb >= 16:
                return "4G", "6G"
            elif total_ram_gb >= 8:
                return "2G", "4G"
            elif total_ram_gb >= 4:
                return "1G", "2G"
            else:
                return "512M", "1G"
        except Exception:
            # Safe defaults
            return "2G", "4G"
    
    def detect_world_folder(self, server_dir: str) -> str:
        """Detect world folder name"""
        common_names = ["world", "world_the_end", "world_nether"]
        
        for name in common_names:
            if os.path.exists(os.path.join(server_dir, name)):
                return "world"  # Always use "world" as the main folder
        
        return "world"
    
    def generate_config(self, interactive: bool = False) -> dict:
        """Generate complete config with defaults"""
        
        # Detect settings
        server_dir = self.detect_server_directory()
        server_jar = self.detect_server_jar(server_dir)
        java_path = self.detect_java_path()
        java_xms, java_xmx = self.calculate_java_memory()
        world_folder = self.detect_world_folder(server_dir)
        
        # Build config with intelligent defaults
        self.config = {
            "rcon_host": "127.0.0.1",
            "rcon_port": 25575,
            "command_channel_id": 0,  # Will be auto-created
            "log_channel_id": 0,      # Will be auto-created
            "debug_channel_id": 0,    # Will be auto-created
            "owner_role_id": 0,       # Deprecated but kept for compatibility
            "server_directory": server_dir,
            "server_jar": server_jar,
            "java_path": java_path,
            "world_folder": world_folder,
            "java_xms": java_xms,
            "java_xmx": java_xmx,
            "backup_time": "22:00",
            "backup_retention_days": 7,
            "restart_time": "00:00",
            "restart_delay_s": 5,
            "crash_check_interval_s": 30,
            "log_lines_default": 10,
            "status_cooldown_s": 5,
            "logs_cooldown_s": 10,
            "guild_id": "",           # Will be auto-detected
            "intentional_stop": os.path.join(server_dir, "bot_state.json"),
            "roles": {},              # Will be auto-created by setup_helper
            "timezone": "Europe/Ljubljana"
        }
        
        return self.config
    
    def save_config(self, path: str = "config.json"):
        """Save config to file"""
        with open(path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        # Secure the file
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass  # Windows doesn't support chmod the same way
    
    def load_or_generate(self, path: str = "config.json") -> dict:
        """Load existing config or generate new one"""
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        else:
            print("🔧 Generating config.json with intelligent defaults...")
            self.generate_config()
            self.save_config(path)
            print(f"✅ Created {path} with auto-detected settings")
            print(f"   Server directory: {self.config['server_directory']}")
            print(f"   Server jar: {self.config['server_jar']}")
            print(f"   Java memory: {self.config['java_xms']}-{self.config['java_xmx']}")
            return self.config


if __name__ == "__main__":
    # Test the generator
    gen = ConfigGenerator()
    config = gen.generate_config()
    
    print("Generated config:")
    print(json.dumps(config, indent=2))
