import logging
import sys
import asyncio
from utils.ws_manager import ConnectionManager

class WebSocketLogHandler(logging.Handler):
    def __init__(self, ws_manager: ConnectionManager):
        super().__init__()
        self.ws_manager = ws_manager

    def emit(self, record):
        try:
            msg = self.format(record)
            # Schedule broadcast without blocking the logger
            asyncio.create_task(self.ws_manager.broadcast({
                "type": "log",
                "level": record.levelname,
                "message": msg,
                "module": record.name,
                "timestamp": record.created
            }))
        except Exception:
            self.handleError(record)

def setup_logger(name: str, ws_manager: ConnectionManager = None):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if reloaded
    if not logger.handlers:
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # WebSocket handler
        if ws_manager:
            wsh = WebSocketLogHandler(ws_manager)
            wsh.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(wsh)
            
    return logger