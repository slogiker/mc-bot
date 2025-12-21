from abc import ABC, abstractmethod

class ServerInterface(ABC):
    @abstractmethod
    async def start(self):
        pass

    @abstractmethod
    async def stop(self):
        pass

    @abstractmethod
    async def restart(self):
        pass

    @abstractmethod
    def is_running(self) -> bool:
        pass

    @abstractmethod
    def send_command(self, cmd: str):
        pass

    @abstractmethod
    def is_intentionally_stopped(self) -> bool:
        pass
