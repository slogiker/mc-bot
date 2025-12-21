import logging
import sys
import os
import zipfile
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# --- Custom Formatter for [HH:MM:SS - DD.MM.YYYY] ---
class CustomFormatter(logging.Formatter):
    def format(self, record):
        timestamp = datetime.now().strftime('%H:%M:%S - %d.%m.%Y')
        return f"[{timestamp}] {record.levelname:<8} {record.msg}"

# --- Redirect Terminal Output to Logger ---
class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.buffer = ''

    def write(self, buf):
        self.buffer += buf
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.logger.log(self.level, f"[TERMINAL] {line}")

    def flush(self):
        if self.buffer and self.buffer.strip():
            self.logger.log(self.level, f"[TERMINAL] {self.buffer}")
            self.buffer = ''

def namer(name):
    return name + ".zip"

def rotator(source, dest):
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(source, os.path.basename(source))
    os.remove(source)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear any existing handlers

    formatter = CustomFormatter()
    
    # Weekly rotation (W0 = Monday), keep 4 weeks
    file_handler = TimedRotatingFileHandler('bot.log', when='W0', interval=1, backupCount=4)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    file_handler.namer = namer
    file_handler.rotator = rotator
    
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # Redirect stderr to logger
    sys.stderr = StreamToLogger(logger, logging.ERROR)
    
    return logger

logger = setup_logging()
