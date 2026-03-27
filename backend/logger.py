import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Merge structured dictionary data explicitly
        if hasattr(record, "structured_metadata"):
            log_obj.update(record.structured_metadata)
            
        return json.dumps(log_obj)

def get_structured_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    # Prevent duplicate console noise via root
    logger.propagate = False
    return logger
