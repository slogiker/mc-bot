import json
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.load()
        return cls._instance

    def load(self):
        self.TOKEN = os.getenv("BOT_TOKEN")
        self.RCON_PASSWORD = os.getenv("RCON_PASSWORD")
        self.TEST_BOT_TOKEN = os.getenv("TEST_BOT_TOKEN")
        self.TEST_MODE = False # Default, can be overridden
        self.DRY_RUN_MODE = False # Default, can be overridden

        with open('config.json', 'r') as f:
            data = json.load(f)
            
        self.RCON_HOST = data['rcon_host']
        self.RCON_PORT = data['rcon_port']
        self.COMMAND_CHANNEL_ID = data['command_channel_id']
        self.LOG_CHANNEL_ID = data['log_channel_id']
        self.DEBUG_CHANNEL_ID = data['debug_channel_id']
        self.ADMIN_ROLE_ID = data['owner_role_id']
        self.SERVER_DIR = data['server_directory']
        self.SERVER_JAR = data['server_jar']
        self.WORLD_FOLDER = data.get('world_folder', 'world')
        self.JAVA_XMS = data['java_xms']
        self.JAVA_XMX = data['java_xmx']
        self.BACKUP_TIME = data['backup_time']
        self.BACKUP_RETENTION_DAYS = data['backup_retention_days']
        self.RESTART_TIME = data['restart_time']
        self.RESTART_DELAY = data['restart_delay_s']
        self.CRASH_CHECK_INTERVAL = data['crash_check_interval_s']
        self.LOG_LINES_DEFAULT = data['log_lines_default']
        self.STATUS_COOLDOWN = data['status_cooldown_s']
        self.LOGS_COOLDOWN = data['logs_cooldown_s']
        self.GUILD_ID = data['guild_id']
        self.STATE_FILE = data['intentional_stop']
        self.ROLES = data['roles']
        self.JAVA_PATH = data.get("java_path", "java")
        self.TIMEZONE = data.get("timezone", "Europe/Ljubljana")

    def set_test_mode(self, enabled: bool):
        self.TEST_MODE = enabled

    def set_dry_run_mode(self, enabled: bool):
        self.DRY_RUN_MODE = enabled

    def override_channel_ids(self, command_id: int, log_id: int, debug_id: int):
        self.COMMAND_CHANNEL_ID = command_id
        self.LOG_CHANNEL_ID = log_id
        self.DEBUG_CHANNEL_ID = debug_id

    def update_dynamic_config(self, updates: dict):
        """Update config with dynamically found IDs."""
        if 'command_channel_id' in updates:
            self.COMMAND_CHANNEL_ID = updates['command_channel_id']
        if 'log_channel_id' in updates:
            self.LOG_CHANNEL_ID = updates['log_channel_id']
        if 'debug_channel_id' in updates:
            self.DEBUG_CHANNEL_ID = updates['debug_channel_id']
        if 'roles' in updates:
            self.ROLES = updates['roles']

config = Config()
