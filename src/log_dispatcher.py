import asyncio
from src.logger import logger
from collections import deque

class LogDispatcher:
    def __init__(self):
        self._subscribers = []
        self._running = False
        self._task = None
        self._buffer = deque(maxlen=50)
        self._process = None

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def get_recent_logs(self) -> list:
        """Return the last 50 lines of logs."""
        return list(self._buffer)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._tail_logs())

    async def stop(self):
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                await self._process.wait()
            except Exception:
                pass
            self._process = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _tail_logs(self):
        from src.config import config
        import os
        
        log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
        logger.info(f"LogDispatcher: Starting tail of {log_path}")
        
        while self._running:
            try:
                if not os.path.exists(log_path):
                    await asyncio.sleep(2)
                    continue
                
                logger.info("LogDispatcher: Starting tail -F subprocess")
                
                # Use tail -F for instant line delivery (follows file renames/rotations)
                self._process = await asyncio.create_subprocess_exec(
                    "tail", "-F", "-n", "0", log_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL
                )
                
                while self._running and self._process.returncode is None:
                    try:
                        line_bytes = await asyncio.wait_for(
                            self._process.stdout.readline(),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        continue
                    
                    if not line_bytes:
                        # Process ended
                        break
                    
                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    # Store in rolling buffer
                    self._buffer.append(line)
                    
                    # Broadcast to all subscribers
                    for q in self._subscribers.copy():
                        try:
                            q.put_nowait(line)
                        except asyncio.QueueFull:
                            pass
                
                # Process ended, clean up and retry
                if self._process:
                    try:
                        self._process.terminate()
                        await self._process.wait()
                    except Exception:
                        pass
                    self._process = None
                
                logger.warning("LogDispatcher: tail process ended, restarting...")
                await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"LogDispatcher error: {e}")
                if self._process:
                    try:
                        self._process.terminate()
                    except Exception:
                        pass
                    self._process = None
                await asyncio.sleep(5)

log_dispatcher = LogDispatcher()
