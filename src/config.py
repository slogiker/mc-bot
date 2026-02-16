import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from filelock import FileLock

load_dotenv()

def validate_user_config(data: dict) -> tuple[bool, list[str]]:
    """Validate user config without external packages"""
    errors = []
    
    # RAM format validation
    for key in ['java_ram_min', 'java_ram_max']:
        if key not in data:
            errors.append(f"Missing required field: {key}")
            continue
        if not re.match(r'^\d+[MG]$', data[key]):
            errors.append(f"{key} must be like '4G' or '2048M'")
    
    # Check min <= max
    if 'java_ram_min' in data and 'java_ram_max' in data:
        try:
            min_val = int(data['java_ram_min'][:-1])
            max_val = int(data['java_ram_max'][:-1])
            min_unit = data['java_ram_min'][-1]
            max_unit = data['java_ram_max'][-1]
            
            # Convert to MB for comparison
            min_mb = min_val if min_unit == 'M' else min_val * 1024
            max_mb = max_val if max_unit == 'M' else max_val * 1024
            
            if min_mb > max_mb:
                errors.append("java_ram_min must be <= java_ram_max")
        except:
            pass
    
    # Time format (HH:MM)
    for key in ['backup_time', 'restart_time']:
        if key not in data:
            errors.append(f"Missing required field: {key}")
            continue
        try:
            datetime.strptime(data[key], '%H:%M')
        except:
            errors.append(f"{key} must be HH:MM format (e.g., '03:00')")
    
    # Keep days range
    if 'backup_keep_days' not in data:
        errors.append("Missing required field: backup_keep_days")
    elif not isinstance(data['backup_keep_days'], int) or not 1 <= data['backup_keep_days'] <= 365:
        errors.append("backup_keep_days must be an integer between 1 and 365")
    
    # Timezone
    if 'timezone' not in data:
        errors.append("Missing required field: timezone")
    
    # Permissions
    if 'permissions' not in data:
        errors.append("Missing required field: permissions")
    elif not isinstance(data['permissions'], dict):
        errors.append("permissions must be an object/dictionary")
    
    return len(errors) == 0, errors


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.BOT_CONFIG_FILE = os.path.join('data', 'bot_config.json')
            cls._instance.USER_CONFIG_FILE = os.path.join('data', 'user_config.json')
            cls._instance.load()
        return cls._instance

    def load(self):
        self.TOKEN = os.getenv("BOT_TOKEN")
        self.RCON_PASSWORD = os.getenv("RCON_PASSWORD")
        self.dry_run = False  # Default, set via command line flag
        
        # Check for old config.json and migrate
        if os.path.exists('config.json') and not os.path.exists(os.path.join('data', 'user_config.json')):
            self._migrate_old_config()
        
        # Load user config
        try:
            with open(os.path.join('data', 'user_config.json'), 'r') as f:
                user_cfg = json.load(f)
        except FileNotFoundError:
            print("❌ user_config.json not found! Creating default...")
            self._create_default_configs()
            with open(os.path.join('data', 'user_config.json'), 'r') as f:
                user_cfg = json.load(f)
        
        # Validate
        valid, errors = validate_user_config(user_cfg)
        if not valid:
            error_msg = "❌ Invalid user_config.json:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
        
        # Load bot config
        try:
            bot_cfg = self.load_bot_config()
        except Exception:
            print("❌ bot_config.json not found! Creating default...")
            self._create_default_configs()
            bot_cfg = self.load_bot_config()
        
        # Apply user config
        self.JAVA_XMX = user_cfg['java_ram_max']
        self.JAVA_XMS = user_cfg['java_ram_min']
        self.BACKUP_TIME = user_cfg['backup_time']
        self.BACKUP_RETENTION_DAYS = user_cfg['backup_keep_days']
        self.RESTART_TIME = user_cfg['restart_time']
        self.TIMEZONE = user_cfg.get('timezone', 'UTC')
        self.ROLE_PERMISSIONS = user_cfg['permissions']
        
        # Apply bot config
        self.SERVER_DIR = bot_cfg['server_directory']
        self.GUILD_ID = bot_cfg.get('guild_id')
        self.COMMAND_CHANNEL_ID = bot_cfg.get('command_channel_id')
        self.LOG_CHANNEL_ID = bot_cfg.get('log_channel_id')
        self.DEBUG_CHANNEL_ID = bot_cfg.get('debug_channel_id')
        self.SPAWN_X = bot_cfg.get('spawn_x')
        self.SPAWN_Y = bot_cfg.get('spawn_y')
        self.SPAWN_Z = bot_cfg.get('spawn_z')
        
        # Hardcoded/default values (not user-configurable)
        # TODO: Make RCON_HOST configurable for multi-container setups
        self.RCON_HOST = "127.0.0.1"

        self.RCON_PORT = 25575
        self.SERVER_JAR = "server.jar"
        self.WORLD_FOLDER = "world"
        self.JAVA_PATH = "java"
        self.RESTART_DELAY = 5
        self.CRASH_CHECK_INTERVAL = 30
        self.LOG_LINES_DEFAULT = 10
        self.STATUS_COOLDOWN = 5
        self.LOGS_COOLDOWN = 10
        self.STATE_FILE = os.path.join(self.SERVER_DIR, 'bot_state.json')
        
        # Legacy: Create ROLES dict with ID -> commands mapping (populated at runtime)
        self.ROLES = {}
        self.ADMIN_ROLE_ID = None  # Set during setup

    def _migrate_old_config(self):
        """Migrate from old config.json to new split config"""
        print("🔄 Migrating old config.json to new format...")
        
        try:
            with open('config.json', 'r') as f:
                old_cfg = json.load(f)
            
            # Create user_config.json
            user_cfg = {
                "java_ram_min": old_cfg.get('java_xms', '2G'),
                "java_ram_max": old_cfg.get('java_xmx', '4G'),
                "backup_time": old_cfg.get('backup_time', '03:00'),
                "backup_keep_days": old_cfg.get('backup_retention_days', 7),
                "restart_time": old_cfg.get('restart_time', '04:00'),
                "timezone": old_cfg.get('timezone', 'UTC'),
                "permissions": self._convert_old_roles(old_cfg.get('roles', {}))
            }
            
            with open(os.path.join('data', 'user_config.json'), 'w') as f:
                json.dump(user_cfg, f, indent='\t')
            
            # Create bot_config.json
            bot_cfg = {
                "server_directory": old_cfg.get('server_directory', './mc-server'),
                "guild_id": old_cfg.get('guild_id'),
                "command_channel_id": old_cfg.get('command_channel_id'),
                "log_channel_id": old_cfg.get('log_channel_id'),
                "debug_channel_id": old_cfg.get('debug_channel_id')
            }
            
            with open(os.path.join('data', 'bot_config.json'), 'w') as f:
                json.dump(bot_cfg, f, indent='\t')
            
            # Backup old config
            os.rename('config.json', 'config.json.backup')
            print("✅ Migration complete! Old config backed up to config.json.backup")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise
    
    def _convert_old_roles(self, old_roles: dict) -> dict:
        """Convert old role ID-based permissions to default role names"""
        # Just return default permissions, user can customize
        return {
            "MC Admin": [
                "start", "stop", "restart", "cmd", "backup_now",
                "reload_config", "shutdown", "bot_stop", "bot_restart",
                "logs", "whitelist_add", "seed", "players", "stats",
                "version", "server_info", "mods", "help", "sync"
            ],
            "MC Player": [
                "status", "start", "players", "stop", "restart",
                "logs", "whitelist_add", "seed", "version",
                "server_info", "mods", "backup_now", "stats", "help"
            ],
            "@everyone": [
                "status", "help", "players", "seed", "server_info", "mods", "stats"
            ]
        }
    
    def _create_default_configs(self):
        """Create default config files"""
        user_cfg = {
            "java_ram_min": "2G",
            "java_ram_max": "4G",
            "backup_time": "03:00",
            "backup_keep_days": 7,
            "restart_time": "04:00",
            "timezone": "Europe/Ljubljana",
            "permissions": self._convert_old_roles({})
        }
        
        bot_cfg = {
            "server_directory": "./mc-server",
            "guild_id": None,
            "command_channel_id": None,
            "log_channel_id": None,
            "debug_channel_id": None
        }
        
        # In simulation, we don't write defaults to disk
        if not self.dry_run:
            try:
                os.makedirs('data', exist_ok=True)
            except OSError:
                pass # Ignore if exists
                
            with open(os.path.join('data', 'user_config.json'), 'w') as f:
                json.dump(user_cfg, f, indent='\t')
            
            with open(os.path.join('data', 'bot_config.json'), 'w') as f:
                json.dump(bot_cfg, f, indent='\t')
        else:
             print("👻 Simulation Mode: Skipping default config creation")

    def set_simulation_mode(self, enabled: bool):
        """Enable/disable simulation/ghost mode"""
        self.dry_run = enabled
        if enabled:
            from src.logger import logger
            logger.info("👻 SIMULATION MODE ENABLED - No files will be written")

    def override_channel_ids(self, command_id: int, log_id: int, debug_id: int):
        self.COMMAND_CHANNEL_ID = command_id
        self.LOG_CHANNEL_ID = log_id
        self.DEBUG_CHANNEL_ID = debug_id

    def update_dynamic_config(self, updates: dict):
        """Update memory config with dynamically found IDs"""
        for key, value in updates.items():
            attr_name = key.upper()
            if hasattr(self, attr_name):
                setattr(self, attr_name, value)
            elif key == 'installed_version':
                self.INSTALLED_VERSION = value

    def load_bot_config(self) -> dict:
        """Load the bot configuration with file locking."""
        lock = FileLock(self.BOT_CONFIG_FILE + ".lock")
        with lock:
            if not os.path.exists(self.BOT_CONFIG_FILE):
                return {}
            with open(self.BOT_CONFIG_FILE, 'r') as f:
                return json.load(f)

    def save_bot_config(self, data: dict):
        """Save the bot configuration with file locking."""
        lock = FileLock(self.BOT_CONFIG_FILE + ".lock")
        os.makedirs(os.path.dirname(self.BOT_CONFIG_FILE), exist_ok=True)
        with lock:
            with open(self.BOT_CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent='\t')
        # Refresh current config object
        self.load()

    def load_user_config(self) -> dict:
        """Load user preferences with file locking."""
        lock = FileLock(self.USER_CONFIG_FILE + ".lock")
        with lock:
            if not os.path.exists(self.USER_CONFIG_FILE):
                return {}
            with open(self.USER_CONFIG_FILE, 'r') as f:
                return json.load(f)

    def save_user_config(self, data: dict):
        """Save user preferences with file locking."""
        lock = FileLock(self.USER_CONFIG_FILE + ".lock")
        os.makedirs(os.path.dirname(self.USER_CONFIG_FILE), exist_ok=True)
        with lock:
            with open(self.USER_CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent='\t')
        # Refresh current config object
        self.load()
    
    def resolve_role_permissions(self, guild):
        """Resolve role names to IDs for permission checking"""
        self.ROLES = {}
        
        for role_name, commands in self.ROLE_PERMISSIONS.items():
            if role_name == "@everyone":
                # Use guild's default role
                self.ROLES[str(guild.default_role.id)] = commands
            else:
                # Find role by name
                role = discord.utils.get(guild.roles, name=role_name)
                if role:
                    self.ROLES[str(role.id)] = commands
                else:
                    from src.logger import logger
                    logger.warning(f"Role '{role_name}' not found in guild")
    
    def get(self, key, default=None):
        """Get config value safely (case-insensitive key lookup)"""
        # Try to find attribute directly
        if hasattr(self, key.upper()):
            val = getattr(self, key.upper())
            if val is not None:
                return val
        
        # Try finding in other maps if needed, but for now just return default
        return default

config = Config()
