import asyncio
import re
from src.logger import logger
from src.log_dispatcher import log_dispatcher

class LogWatcher:
    """
    Consumes logs from the centralized LogDispatcher to detect when a player connects.
    We look for the 'User Authenticator' line because it contains the UUID *before* they are fully joined,
    allowing us to intercept and potentially kick them.
    
    Target Line:
    [10:22:34] [User Authenticator #1/INFO]: UUID of player slogiker is 1234abcd-5678-...
    """
    def __init__(self, bot):
        self.bot = bot
        self._task = None
        self._running = False
        self._queue = None
        
        # Regex to capture Username and UUID from Vanilla/Paper/Fabric logs
        # Login: fires before player is fully in-game — used for JoinGuard
        self.auth_pattern = re.compile(
            r'\[(?:[0-9:]+)\] \[User Authenticator #\d+/INFO\].*?UUID of player (?P<username>[A-Za-z0-9_]+) is (?P<uuid>[0-9a-fA-F-]+)'
        )
        
        # Fallback regex for Forge/NeoForge which sometimes formats differently
        self.auth_pattern_forge = re.compile(
            r'\[(?:[0-9:]+)\] \[Netty(?:[a-zA-Z0-9 _#-]+)?/INFO\].*?: UUID of player (?P<username>[A-Za-z0-9_]+) is (?P<uuid>[0-9a-fA-F-]+)'
        )

        # Leave
        self.leave_pattern = re.compile(
            r'\[(?:[0-9:]+)\] \[Server thread/INFO\].*?(?P<username>[A-Za-z0-9_]+) left the game'
        )

        # Collision (impersonation detection)
        self.collision_pattern = re.compile(
            r'\[(?:[0-9:]+)\] \[.*?/INFO\].*?(?P<username>[A-Za-z0-9_]+) lost connection: You logged in from another location'
        )


    def start(self):
        if self._task is None or self._task.done():
            # Clean up old queue if exists
            if self._queue:
                log_dispatcher.unsubscribe(self._queue)
                
            self._running = True
            self._queue = log_dispatcher.subscribe()
            self._task = asyncio.create_task(self._process_logs())
            logger.info("Started Minecraft Log Watcher (via LogDispatcher)")

    def stop(self):
        if self._running:
            self._running = False
            if self._queue:
                log_dispatcher.unsubscribe(self._queue)
                self._queue = None
            if self._task:
                self._task.cancel()
            logger.info("Stopped Minecraft Log Watcher")
            
    async def _process_logs(self):
        try:
            while self._running and self._queue:
                line = await self._queue.get()
                self._check_line(line)
        except asyncio.CancelledError:
            pass

    def _check_line(self, line: str):
        # 1. Login match
        auth_match = self.auth_pattern.search(line) or self.auth_pattern_forge.search(line)
        if auth_match:
            username = auth_match.group('username')
            uuid = auth_match.group('uuid')
            self.bot.dispatch('minecraft_player_login', username, uuid)
            return

        # 2. Leave match
        leave_match = self.leave_pattern.search(line)
        if leave_match:
            username = leave_match.group('username')
            self.bot.dispatch('minecraft_player_quit', username)
            return

        # 3. Collision match
        collision_match = self.collision_pattern.search(line)
        if collision_match:
            username = collision_match.group('username')
            self.bot.dispatch('minecraft_collision', username)
            return
