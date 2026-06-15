import subprocess
import asyncio
import os
import json
import shlex
import time
import aiofiles
from src.server_interface import ServerInterface
from src.config import config
from src.logger import logger

class TmuxServerManager(ServerInterface):
    def __init__(self):
        self.session_name = "minecraft"
        self._intentional_stop = True  # Cache in memory to avoid blocking I/O
        self._start_time = None
        self._state_file = os.path.join(config.SERVER_DIR, 'bot_state.json')
        self._state_lock = asyncio.Lock()  # Prevent race conditions

        # Cache status for 5 seconds to prevent flickering
        self._cached_is_running = False
        self._last_status_check = 0
        self._status_cache_ttl = 5

    def _run_tmux_cmd(self, args):
        """Run tmux command synchronously (only used for quick checks)"""
        try:
            cmd = ["tmux"] + args
            return subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            logger.error("Tmux command timed out")
            return subprocess.CompletedProcess(args, 1, "", "Command timed out")
        except FileNotFoundError:
            logger.error("Tmux not found in PATH")
            return subprocess.CompletedProcess(args, 1, "", "Tmux not found")
        except Exception as e:
            logger.error(f"Error running tmux command: {e}")
            return subprocess.CompletedProcess(args, 1, "", str(e))

    def is_running(self) -> bool:
        """Check if tmux session exists (cached for 5s)"""
        now = time.time()
        if now - self._last_status_check < self._status_cache_ttl:
            return self._cached_is_running

        try:
            res = self._run_tmux_cmd(["has-session", "-t", self.session_name])
            self._cached_is_running = (res.returncode == 0)
            self._last_status_check = now
            return self._cached_is_running
        except Exception as e:
            logger.error(f"Error checking if server is running: {e}")
            return False

    def is_intentionally_stopped(self) -> bool:
        """Return cached state (non-blocking)"""
        return self._intentional_stop
        
    def get_start_time(self) -> float | None:
        return self._start_time

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
                        self._start_time = data.get('start_time')
                        logger.info(f"Loaded state: intentional_stop={self._intentional_stop}, start_time={self._start_time}")
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
                state_dir = os.path.dirname(self._state_file)
                if state_dir:
                    await asyncio.to_thread(os.makedirs, state_dir, exist_ok=True)
                
                data = {
                    'intentional_stop': self._intentional_stop,
                    'start_time': self._start_time
                }
                async with aiofiles.open(self._state_file, 'w') as f:
                    await f.write(json.dumps(data, indent=2))
                logger.info(f"Saved state: intentional_stop={self._intentional_stop}, start_time={self._start_time}")
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

        world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
        world_exists = await asyncio.to_thread(os.path.exists, world_path)

        # Self-healing: If jar exists but world is missing, try to generate it
        if jar_exists and not world_exists:
            logger.warning("World folder missing but server.jar exists. Attempting auto-generation (watching logs for 'Done')...")
            
            # Start the process in the background
            try:
                proc = await asyncio.create_subprocess_exec(
                    "java", "-jar", config.SERVER_JAR, "nogui",
                    cwd=config.SERVER_DIR,
                    stdin=subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Watch the output for 'Done' or errors
                done_detected = False
                # Max 5 minutes for extremely slow generation
                try:
                    async with asyncio.timeout(300.0):
                        while True:
                            line = await proc.stdout.readline()
                            if not line:
                                break
                            decoded_line = line.decode('utf-8', errors='ignore').strip()
                            if "Done" in decoded_line and "For help, type" in decoded_line:
                                logger.info(f"Auto-generation finished successfully: {decoded_line}")
                                done_detected = True
                                # Stop the server gracefully since it generated the files
                                proc.stdin.write(b"stop\n")
                                await proc.stdin.drain()
                                break
                            elif "Failed to load properties from file" in decoded_line:
                                logger.warning("First run EULA/properties generation detected.")
                                # Often it stops itself here, let it finish naturally
                except asyncio.TimeoutError:
                    logger.error("Auto-generation timed out after 5 minutes.")
                
                # Ensure the process is dead before continuing
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    
            except Exception as e:
                logger.error(f"Auto-generation of world folder failed: {e}")

            # Re-check
            world_exists = await asyncio.to_thread(os.path.exists, world_path)
            if not world_exists:
                return False, "❌ World folder is missing and auto-generation failed. Please run **/setup** to repair the installation."

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
        
        res = await asyncio.to_thread(
            self._run_tmux_cmd,
            ["new-session", "-d", "-s", self.session_name, "bash", "-c", java_cmd]
        )
        
        if res.returncode != 0:
            msg = f"Failed to start tmux: {res.stderr}"
            logger.error(msg)
            return False, msg
        
        self._intentional_stop = False
        self._start_time = time.time()
        await self._save_state()
        
        # Immediate crash detection (Wait longer for slower hardware like CM4)
        await asyncio.sleep(10)
        if not self.is_running():
            logger.error("Server process died immediately after starting.")
            self._intentional_stop = True # Reset state on failure
            await self._save_state()

            # Check for world folder
            world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
            world_exists = await asyncio.to_thread(os.path.exists, world_path)
            if not world_exists:
                return False, "❌ Server crashed before creating the world folder. This usually means the installation was incomplete. Please run **/setup** again."
            return False, "❌ Server crashed immediately. Check crash-reports/ or logs/latest.log for details."

        logger.info("Server started successfully")
        return True, "Server started successfully"

    async def stop(self) -> tuple[bool, str]:
        """Stop the Minecraft server"""
        if not self.is_running():
            logger.info("Server is not running.")
            return False, "Server is not running"
        
        # Mark as intentional stop FIRST
        self._intentional_stop = True
        self._start_time = None
        await self._save_state()
        
        # Send stop command via tmux
        logger.info("Sending stop command to server...")
        self.send_command("stop")
        
        # Wait for graceful shutdown via logs
        from src.log_dispatcher import log_dispatcher
        # Waiting for "Thread RCON Listener stopped" or "Stopping server" ensures it's shutting down safely.
        # It can take over 30s to save a large world on slow hardware.
        if not await log_dispatcher.wait_for_pattern("Thread RCON Listener stopped", timeout=60):
            logger.warning("Server didn't stop gracefully within 60s, killing tmux session")
            await self.emergency_stop()
        else:
            # Give it 3 more seconds to fully exit the java process after RCON closes
            await asyncio.sleep(3)
            if self.is_running():
                await self.emergency_stop()
        
        logger.info("Server stopped successfully")
        return True, "Server stopped successfully"

    async def emergency_stop(self) -> tuple[bool, str]:
        """Forcefully stop the server by killing the tmux session"""
        logger.warning("Forcefully killing tmux session")
        self._intentional_stop = True
        self._start_time = None
        await self._save_state()
        
        res = await asyncio.to_thread(
            self._run_tmux_cmd,
            ["kill-session", "-t", self.session_name]
        )
        if res.returncode == 0:
            return True, "Server forcefully stopped"
        else:
            return False, f"Failed to kill tmux session: {res.stderr}"

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
            self._run_tmux_cmd(["send-keys", "-t", self.session_name, "--", cmd, "C-m"])
            logger.info(f"Sent command to server: {cmd}")
        except Exception as e:
            logger.error(f"Failed to send command: {e}")