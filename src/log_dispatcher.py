import asyncio
from src.logger import logger
from collections import deque

class LogDispatcher:
    def __init__(self):
        self._subscribers = []
        self._running = False
        self._task = None
        self._buffer = deque(maxlen=50)

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
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _tail_logs(self):
        from src.config import config
        import os
        import aiofiles
        
        log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
        logger.info(f"LogDispatcher: Starting tail of {log_path}")
        
        while self._running:
            try:
                if not os.path.exists(log_path):
                    await asyncio.sleep(2)
                    continue
                    
                logger.info("LogDispatcher: Connected to latest.log stream")
                async with aiofiles.open(log_path, mode='r', encoding='utf-8', errors='ignore') as f:
                    # Seek to the end of the file
                    await f.seek(0, 2)
                    
                    while self._running:
                        line = await f.readline()
                        if not line:
                            await asyncio.sleep(0.1)
                            
                            # Check if the file was rotated/truncated (size became smaller than current position)
                            current_pos = await f.tell()
                            if os.path.exists(log_path) and os.path.getsize(log_path) < current_pos:
                                logger.info("LogDispatcher: latest.log seems rotated, reconnecting...")
                                break
                            continue
                            
                        line = line.strip()
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
                                
            except Exception as e:
                logger.error(f"LogDispatcher error: {e}")
                await asyncio.sleep(5)

log_dispatcher = LogDispatcher()
