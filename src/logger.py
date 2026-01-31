import logging
import sys
import os
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
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

# --- Monthly Log Zipper ---
class MonthlyLogZipper:
    """Handles monthly organization and zipping of log files"""
    
    def __init__(self, logs_dir):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.last_checked_month = None
    
    def check_and_zip_month(self):
        """Check if we need to zip logs from previous month"""
        try:
            current_month = datetime.now().strftime('%Y-%m')
            
            # Only check once per month
            if self.last_checked_month == current_month:
                return
            
            # Check for previous month's directory
            if self.last_checked_month and self.last_checked_month != current_month:
                self._zip_month_directory(self.last_checked_month)
            
            self.last_checked_month = current_month
        except Exception as e:
            # Don't let logging errors break the application
            try:
                logging.getLogger().error(f"Error in monthly log zipper: {e}")
            except:
                pass
    
    def _zip_month_directory(self, month_str):
        """Zip all log files in a month directory"""
        try:
            month_dir = self.logs_dir / month_str
            if not month_dir.exists():
                return
            
            # Get all log files (not already zipped)
            log_files = [f for f in month_dir.iterdir() if f.is_file() and not f.name.endswith('.zip')]
            if not log_files:
                # Try to remove empty directory
                try:
                    month_dir.rmdir()
                except OSError:
                    pass
                return
            
            # Create zip file for the month
            zip_path = self.logs_dir / f"{month_str}_logs.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for log_file in log_files:
                    try:
                        zf.write(log_file, log_file.name)
                        log_file.unlink()  # Delete after adding to zip
                    except Exception as e:
                        try:
                            logging.getLogger().error(f"Failed to add {log_file} to zip: {e}")
                        except:
                            pass
            
            # Remove empty month directory
            try:
                month_dir.rmdir()
            except OSError:
                pass  # Directory not empty or doesn't exist
                
        except Exception as e:
            try:
                logging.getLogger().error(f"Failed to zip month {month_str}: {e}")
            except:
                pass

# Global zipper instance
_zipper = None

def namer(name):
    """Custom namer to organize logs by month"""
    global _zipper
    try:
        # Extract date from filename (format: bot.log.YYYY-MM-DD)
        base_name = os.path.basename(name)
        if '.' in base_name:
            parts = base_name.split('.')
            if len(parts) >= 4:  # bot.log.YYYY-MM-DD
                date_part = '.'.join(parts[-3:])  # YYYY-MM-DD
                try:
                    # Validate date format
                    datetime.strptime(date_part, '%Y-%m-%d')
                    month = date_part[:7]  # YYYY-MM
                    
                    # Get logs directory from the original path
                    logs_dir = Path(name).parent
                    month_dir = logs_dir / month
                    month_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Update zipper and check for previous month
                    if _zipper:
                        _zipper.check_and_zip_month()
                    
                    return str(month_dir / base_name)
                except ValueError:
                    pass
    except Exception as e:
        try:
            logging.getLogger().error(f"Error in log namer: {e}")
        except:
            pass
    
    # Fallback: return original name
    return name

def rotator(source, dest):
    """Custom rotator that zips individual log files"""
    try:
        # Zip the rotated file
        with zipfile.ZipFile(dest + '.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(source, os.path.basename(source))
        
        # Remove original rotated file
        if os.path.exists(source):
            os.remove(source)
    except Exception as e:
        # If zipping fails, just keep the file
        try:
            logging.getLogger().error(f"Failed to zip rotated log: {e}")
        except:
            pass

def setup_logging():
    """Setup logging with daily rotation, monthly organization, and zipping"""
    global _zipper
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear any existing handlers

    formatter = CustomFormatter()
    
    # Create logs directory
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Initialize monthly zipper
    _zipper = MonthlyLogZipper(logs_dir)
    _zipper.last_checked_month = datetime.now().strftime('%Y-%m')
    
    # Daily rotation (midnight), keep 31 days of daily logs
    log_file = logs_dir / 'bot.log'
    file_handler = TimedRotatingFileHandler(
        str(log_file), 
        when='midnight', 
        interval=1, 
        backupCount=31,  # Keep 31 days of daily logs before zipping
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    file_handler.namer = namer
    file_handler.rotator = rotator
    
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # Redirect stderr to logger
    sys.stderr = StreamToLogger(logger, logging.ERROR)
    
    return logger

logger = setup_logging()
