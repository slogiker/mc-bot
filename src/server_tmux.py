import subprocess
import asyncio
import os
import json
import aiofiles
from src.server_interface import ServerInterface
from src.config import config
from src.logger import logger

class TmuxServerManager(ServerInterface):
    def __init__(self):
        self.session_name = "minecraft"
        self._intentional_stop = True  # Cache in memory to avoid blocking I/O
        self._state_file = os.path.join(config.SERVER_DIR, 'bot_state.json')
        
        # Load initial state asynchronously later, for now assume intentional stop
        # We'll load it properly on first access

    def _run_tmux_cmd(self, args):
        """Run tmux command synchronously (only used for quick checks)"""
        cmd = ["tmux"] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    def is_running(self) -> bool:
        """Check if tmux session exists (non-blocking subprocess call)"""
        try:
            res = self._run_tmux_cmd(["has-session", "-t", self.session_name])
            return res.returncode == 0
        except Exception as e:
            logger.error(f"Error checking if server is running: {e}")
            return False

    def is_intentionally_stopped(self) -> bool:
        """Return cached state (non-blocking)"""
        return self._intentional_stop

    async def _load_state(self):
        """Load state from file asynchronously"""
        try:
            if os.path.exists(self._state_file):
                async with aiofiles.open(self._state_file, 'r') as f:
                    content = await f.read()
                    data = json.loads(content)
                    self._intentional_stop = data.get('intentional_stop', True)
                    logger.info(f"Loaded state: intentional_stop={self._intentional_stop}")
            else:
                logger.info("No state file found, assuming intentional stop")
                self._intentional_stop = True
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            self._intentional_stop = True

    async def _save_state(self):
        """Save state to file asynchronously"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            
            data = {'intentional_stop': self._intentional_stop}
            async with aiofiles.open(self._state_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
            logger.info(f"Saved state: intentional_stop={self._intentional_stop}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    async def start(self):
        """Start the Minecraft server"""
        if self.is_running():
            logger.info("Server is already running.")
            return False

        # Kill any existing session just in case
        self._run_tmux_cmd(["kill-session", "-t", self.session_name])

        java_cmd = f"cd {config.SERVER_DIR} && {config.JAVA_PATH} -Xms{config.JAVA_XMS} -Xmx{config.JAVA_XMX} -jar {config.SERVER_JAR} nogui"
        
        # Start new session detached
        logger.info(f"Starting server with command: {java_cmd}")
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None, 
            self._run_tmux_cmd, 
            ["new-session", "-d", "-s", self.session_name, "bash", "-c", java_cmd]
        )
        
        if res.returncode != 0:
            logger.error(f"Failed to start tmux session: {res.stderr}")
            return False
        
        # Update state
        self._intentional_stop = False
        await self._save_state()
        
        logger.info("Server started successfully")
        return True

    async def stop(self):
        """Stop the Minecraft server"""
        if not self.is_running():
            logger.info("Server is not running.")
            return False
        
        # Mark as intentional stop FIRST
        self._intentional_stop = True
        await self._save_state()
        
        # Send stop command via tmux
        logger.info("Sending stop command to server...")
        self.send_command("stop")
        
        # Wait a bit for graceful shutdown
        await asyncio.sleep(5)
        
        # If still running, kill the session
        if self.is_running():
            logger.warning("Server didn't stop gracefully, killing tmux session")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._run_tmux_cmd,
                ["kill-session", "-t", self.session_name]
            )
        
        logger.info("Server stopped successfully")
        return True

    async def restart(self):
        """Restart the Minecraft server"""
        logger.info("Restarting server...")
        await self.stop()
        await asyncio.sleep(config.RESTART_DELAY)
        return await self.start()

    def send_command(self, cmd: str):
        """Send command to tmux session (non-blocking)"""
        try:
            # This is a quick operation, so it's OK to be synchronous
            self._run_tmux_cmd(["send-keys", "-t", self.session_name, cmd, "C-m"])
            logger.info(f"Sent command to server: {cmd}")
        except Exception as e:
            logger.error(f"Failed to send command: {e}")