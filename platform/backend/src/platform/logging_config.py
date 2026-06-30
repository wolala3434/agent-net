"""
Structured logging configuration for the Agent Internet Platform.

Configures JSON-formatted logging for production compatibility.
"""

import logging
import sys

try:
    import json_logging
except ImportError:
    json_logging = None


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logs.
    Falls back to standard formatting if json_logging is not available.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_record["data"] = record.extra_data

        try:
            import json
            return json.dumps(log_record, ensure_ascii=False)
        except Exception:
            return super().format(record)


def setup_logging(level: str = "INFO") -> None:
    """
    Initialize structured logging for the platform.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    formatter = JSONFormatter()
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.getLogger("platform").info(f"Logging initialized at level {level}")
