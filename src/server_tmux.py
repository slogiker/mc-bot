import subprocess
import asyncio
import os
import json
from src.server_interface import ServerInterface
from src.config import config
from src.logger import logger

class TmuxServerManager(ServerInterface):
    def __init__(self):
        self.session_name = "minecraft"

    def _run_tmux_cmd(self, args):
        cmd = ["tmux"] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    def is_running(self) -> bool:
        # Check if tmux session exists
        res = self._run_tmux_cmd(["has-session", "-t", self.session_name])
        if res.returncode != 0:
            return False
        
        # Check if java process is running inside it (simplified check)
        # Ideally we check if the process is alive, but tmux session existence is a good proxy
        # provided we kill the session when the server stops.
        return True

    def is_intentionally_stopped(self) -> bool:
        # Check if state file exists and read it
        if os.path.exists(config.STATE_FILE):
             with open(config.STATE_FILE, 'r') as f:
                 try:
                     data = json.load(f)
                     return data.get('intentional_stop', True)
                 except:
                     return True
        return True

    def _set_intentional_stop(self, stopped: bool):
        with open(config.STATE_FILE, 'w') as f:
            json.dump({'intentional_stop': stopped}, f)

    async def start(self):
        if self.is_running():
            logger.info("Server is already running.")
            return False

        # Kill any existing session just in case
        self._run_tmux_cmd(["kill-session", "-t", self.session_name])

        java_cmd = f"cd {config.SERVER_DIR} && {config.JAVA_PATH} -Xms{config.JAVA_XMS} -Xmx{config.JAVA_XMX} -jar {config.SERVER_JAR} nogui"
        
        # Start new session detached
        logger.info(f"Starting server with command: {java_cmd}")
        res = self._run_tmux_cmd(["new-session", "-d", "-s", self.session_name, "bash", "-c", java_cmd])
        
        if res.returncode != 0:
            logger.error(f"Failed to start tmux session: {res.stderr}")
            return False
        
        self._set_intentional_stop(False)
        return True

    async def stop(self):
        if not self.is_running():
            return False
        
        self._set_intentional_stop(True)
        # Send stop command via RCON or stdin
        # Using RCON is safer if available, but here we inject into tmux
        self.send_command("stop")
        
        # Wait for it to close (handled by tasks loop usually, but here we can wait a bit)
        # We don't force kill immediately.
        return True

    async def restart(self):
        await self.stop()
        await asyncio.sleep(config.RESTART_DELAY)
        return await self.start()

    def send_command(self, cmd: str):
        # Send keys to tmux session
        # C-m is Enter
        self._run_tmux_cmd(["send-keys", "-t", self.session_name, cmd, "C-m"])
