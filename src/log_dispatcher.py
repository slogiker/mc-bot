import asyncio
from src.logger import logger

class LogDispatcher:
    def __init__(self):
        self._subscribers = []
        self._running = False
        self._task = None

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._tail_logs())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _tail_logs(self):
        logger.info("LogDispatcher: Starting docker log tailing...")
        while self._running:
            try:
                process = await asyncio.create_subprocess_exec(
                    'docker', 'logs', '-f', '--tail', '0', 'mc-bot',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
                logger.info("LogDispatcher: Connected to docker logs stream")

                while self._running:
                    try:
                        line_bytes = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
                        if not line_bytes:
                            break # EOF
                        line = line_bytes.decode('utf-8', errors='ignore').strip()
                        if not line:
                            continue
                            
                        # Broadcast to all subscribers
                        for q in self._subscribers.copy():
                            try:
                                q.put_nowait(line)
                            except asyncio.QueueFull:
                                pass
                                
                    except asyncio.TimeoutError:
                        continue
                        
                await process.wait()
                if self._running:
                    logger.warning("LogDispatcher: Docker logs process ended, restarting in 5s...")
                    await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"LogDispatcher error: {e}")
                await asyncio.sleep(5)

log_dispatcher = LogDispatcher()
