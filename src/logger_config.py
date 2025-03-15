import logging
import os
import time
from datetime import datetime, timedelta
import threading
import io
import pytz
from telegram import ParseMode

# File to store logs
LOG_FILE = "attendio_bot.log"
log_buffer = io.StringIO()  # In-memory buffer for logs

IST_TIMEZONE = pytz.timezone('Asia/Kolkata')

class TelegramLogHandler(logging.Handler):
    """Custom log handler that collects logs to be sent via Telegram"""
    def __init__(self):
        super().__init__()
        self.log_records = []
        self.max_records = 10000
    
    def emit(self, record):
        log_entry = self.format(record)
        self.log_records.append(log_entry)
        
        # Keep only the last N records to avoid memory issues
        if len(self.log_records) > self.max_records:
            self.log_records = self.log_records[-self.max_records:]
        
        # Also write to file
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry + '\n')

# Configure logging
def setup_logging():
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
            
    # Create our custom handler
    telegram_handler = TelegramLogHandler()
    telegram_handler.setLevel(logging.INFO)
    
    # Create a console handler with higher log level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    class ISTFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            # Convert to IST
            dt = datetime.fromtimestamp(record.created, IST_TIMEZONE)
            if datefmt:
                return dt.strftime(datefmt)
            else:
                return dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3] + " IST"
                
    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    telegram_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add the handlers to the logger
    logger.addHandler(telegram_handler)
    logger.addHandler(console_handler)

    logger.info("========== LOGGING SYSTEM STARTED ==========")
    logger.info(f"Current time in IST: {datetime.now(IST_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
    
    return logger, telegram_handler

# Function to send logs via Telegram
def send_logs_to_admin(bot, admin_id, hours=24):
    import pytz
    try:
        logging.info(f"Collecting logs from the last {hours} hours for admin")
        
        # Get handler
        for handler in logging.getLogger().handlers:
            if isinstance(handler, TelegramLogHandler):
                telegram_handler = handler
                break
        else:
            logging.error("TelegramLogHandler not found")
            return
        
        # Get logs from the last N hours
        cutoff_time = datetime.now(pytz.timezone('Asia/Kolkata')) - timedelta(hours=hours)
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Filter logs based on timestamp
        recent_logs = []
        for log in telegram_handler.log_records:
            # Extract timestamp from log (first part before the first dash)
            try:
                log_time_str = log.split(' - ')[0]
                log_time = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S,%f")
                log_time = IST_TIMEZONE.localize(log_time)
                if log_time >= cutoff_time:
                    recent_logs.append(log)
            except (ValueError, IndexError):
                # If parsing fails, include the log anyway
                recent_logs.append(log)
        
        if not recent_logs:
            bot.send_message(
                chat_id=admin_id, 
                text=f"No logs found from the last {hours} hours."
            )
            logging.info("No logs to send")
            return
        
        # Split logs into chunks (Telegram has a message limit)
        MAX_MESSAGE_LENGTH = 4000
        chunks = []
        current_chunk = []
        current_length = 0
        
        for log in recent_logs:
            # +1 for newline
            if current_length + len(log) + 1 > MAX_MESSAGE_LENGTH:
                chunks.append("\n".join(current_chunk))
                current_chunk = [log]
                current_length = len(log)
            else:
                current_chunk.append(log)
                current_length += len(log) + 1
        
        if current_chunk:
            chunks.append("\n".join(current_chunk))
        
        # Send each chunk
        for i, chunk in enumerate(chunks):
            header = f"📋 Logs ({i+1}/{len(chunks)}) - Last {hours}h:\n\n"
            bot.send_message(
                chat_id=admin_id,
                text=f"{header}```\n{chunk}\n```",
                parse_mode=ParseMode.MARKDOWN
            )
        
        logging.info(f"Sent {len(chunks)} log chunks to admin")
        
    except Exception as e:
        logging.error(f"Failed to send logs via Telegram: {str(e)}")

# Set up daily log sending
def schedule_daily_logs(bot, admin_id):
    """Schedule daily logs to be sent to admin at 5:30 PM IST."""
    from apscheduler.schedulers.background import BackgroundScheduler
    import pytz
    
    try:
        # Create scheduler with explicit timezone
        asia_tz = pytz.timezone('Asia/Kolkata')
        scheduler = BackgroundScheduler()
        
        # Schedule log delivery at 5:30 PM IST daily
        job = scheduler.add_job(
            send_logs_to_admin, 
            'cron', 
            hour=17,  # 5 PM in 24-hour format
            minute=30,  # 30 minutes past the hour
            args=[bot, admin_id, 24],  # Send last 24 hours of logs
            timezone=asia_tz
        )
        
        scheduler.start()
        logging.info(f"Daily log delivery scheduled for 5:30 PM IST (job id: {job.id})")
        
        return scheduler
    except Exception as e:
        logging.error(f"Failed to schedule daily logs: {str(e)}")
        return None
