import subprocess
import asyncio
import os
import json
import shlex
import aiofiles
from src.server_interface import ServerInterface
from src.config import config
from src.logger import logger

class TmuxServerManager(ServerInterface):
    def __init__(self):
        self.session_name = "minecraft"
        self._intentional_stop = True  # Cache in memory to avoid blocking I/O
        self._state_file = os.path.join(config.SERVER_DIR, 'bot_state.json')
        self._state_lock = asyncio.Lock()  # Prevent race conditions
        
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
        async with self._state_lock:
            try:
                # Use asyncio.to_thread for os.path.exists check
                exists = await asyncio.to_thread(os.path.exists, self._state_file)
                if exists:
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
        async with self._state_lock:
            try:
                # Ensure directory exists (use asyncio.to_thread)
                await asyncio.to_thread(os.makedirs, os.path.dirname(self._state_file), exist_ok=True)
                
                data = {'intentional_stop': self._intentional_stop}
                async with aiofiles.open(self._state_file, 'w') as f:
                    await f.write(json.dumps(data, indent=2))
                logger.info(f"Saved state: intentional_stop={self._intentional_stop}")
            except Exception as e:
                logger.error(f"Failed to save state: {e}")

    async def start(self) -> tuple[bool, str]:
        """Start the Minecraft server"""
        if self.is_running():
            logger.info("Server is already running.")
            return False, "Server is already running"

        # Validate paths exist (use asyncio.to_thread)
        jar_path = os.path.join(config.SERVER_DIR, config.SERVER_JAR)
        jar_exists = await asyncio.to_thread(os.path.exists, jar_path)
        if not jar_exists:
            msg = f"Server jar not found: {jar_path}"
            logger.error(msg)
            return False, msg
        
        server_dir_exists = await asyncio.to_thread(os.path.exists, config.SERVER_DIR)
        if not server_dir_exists:
            msg = f"Server directory not found: {config.SERVER_DIR}"
            logger.error(msg)
            return False, msg

        # Kill any existing session just in case
        self._run_tmux_cmd(["kill-session", "-t", self.session_name])

        # Build command with proper escaping to prevent injection
        java_cmd = (
            f"cd {shlex.quote(config.SERVER_DIR)} && "
            f"{shlex.quote(config.JAVA_PATH)} "
            f"-Xms{config.JAVA_XMS} "
            f"-Xmx{config.JAVA_XMX} "
            f"-jar {shlex.quote(config.SERVER_JAR)} "
            f"nogui"
        )
        
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
            msg = f"Failed to start tmux: {res.stderr}"
            logger.error(msg)
            return False, msg
        
        # Update state
        self._intentional_stop = False
        await self._save_state()
        
        logger.info("Server started successfully")
        return True, "Server started successfully"

    async def stop(self) -> tuple[bool, str]:
        """Stop the Minecraft server"""
        if not self.is_running():
            logger.info("Server is not running.")
            return False, "Server is not running"
        
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
        return True, "Server stopped successfully"

    async def restart(self) -> tuple[bool, str]:
        """Restart the Minecraft server"""
        logger.info("Restarting server...")
        stop_success, stop_msg = await self.stop()
        if not stop_success:
            return False, f"Failed to stop server: {stop_msg}"
        
        await asyncio.sleep(config.RESTART_DELAY)
        start_success, start_msg = await self.start()
        
        if start_success:
            return True, "Server restarted successfully"
        else:
            return False, f"Server stopped but failed to restart: {start_msg}"

    def send_command(self, cmd: str):
        """Send command to tmux session (non-blocking)"""
        try:
            # This is a quick operation, so it's OK to be synchronous
            self._run_tmux_cmd(["send-keys", "-t", self.session_name, cmd, "C-m"])
            logger.info(f"Sent command to server: {cmd}")
        except Exception as e:
            logger.error(f"Failed to send command: {e}")