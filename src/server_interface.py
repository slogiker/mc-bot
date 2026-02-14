from abc import ABC, abstractmethod

class ServerInterface(ABC):
    """
    Abstract interface for Minecraft Server Managers.
    Allows swapping between Tmux (Real) and Mock (Simulation) implementations.
    """
    
    @abstractmethod
    def is_running(self) -> bool:
        """Return True if server process is active"""
        pass
        
    @abstractmethod
    def is_intentionally_stopped(self) -> bool:
        """Return True if the server was stopped by user command (not crashed)"""
        pass

    @abstractmethod
    async def start(self) -> tuple[bool, str]:
        """Start the server. Returns (success, message)"""
        pass

    @abstractmethod
    async def stop(self) -> tuple[bool, str]:
        """Stop the server. Returns (success, message)"""
        pass

    @abstractmethod
    async def restart(self) -> tuple[bool, str]:
        """Restart the server. Returns (success, message)"""
        pass

    @abstractmethod
    def send_command(self, cmd: str):
        """Send RCON/Console command to server"""
        pass
