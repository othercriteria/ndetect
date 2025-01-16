"""Logging configuration for ndetect."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from ndetect.types import JsonDict

# Add global variable for logger instance
_logger_instance: Optional["StructuredLogger"] = None


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        # Base log entry with standard fields
        log_entry: JsonDict = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info if available
        if record.pathname and record.lineno:
            log_entry["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add any extra attributes that were passed
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class StructuredLogger(logging.Logger):
    """Logger with additional structured logging capabilities."""

    def info_with_fields(self, message: str, **kwargs: Any) -> None:
        """Log at INFO level with structured fields."""
        extra = {"extra_fields": kwargs}
        self.info(message, extra=extra)

    def error_with_fields(self, message: str, **kwargs: Any) -> None:
        """Log at ERROR level with structured fields."""
        extra = {"extra_fields": kwargs}
        self.error(message, extra=extra)

    def debug_with_fields(self, message: str, **kwargs: Any) -> None:
        """Log at DEBUG level with structured fields."""
        extra = {"extra_fields": kwargs}
        self.debug(message, extra=extra)

    def warning_with_fields(self, message: str, **kwargs: Any) -> None:
        """Log at WARNING level with structured fields."""
        extra = {"extra_fields": kwargs}
        self.warning(message, extra=extra)


# Register our logger class
logging.setLoggerClass(StructuredLogger)


def get_logger() -> "StructuredLogger":
    """Get or create the global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = setup_logging()
    return _logger_instance


def setup_logging(
    log_file: Optional[Path] = None, verbose: bool = False
) -> "StructuredLogger":
    """
    Configure logging for ndetect.

    Args:
        log_file: Optional path to log file. If None, only log to console.
        verbose: If True, set log level to DEBUG.

    Returns:
        StructuredLogger: Configured logger with structured logging capabilities.
    """
    global _logger_instance
    if _logger_instance is not None:
        # If we have an existing logger but need to add a file handler
        if log_file and not any(
            isinstance(h, logging.FileHandler) for h in _logger_instance.handlers
        ):
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(JsonFormatter())
            file_handler.setLevel(logging.DEBUG)
            _logger_instance.addHandler(file_handler)
        return _logger_instance

    # Create logger and explicitly cast to StructuredLogger
    logger = cast(StructuredLogger, logging.getLogger("ndetect"))
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers = []  # Clear any existing handlers

    # Create formatters
    json_formatter = JsonFormatter()
    console_formatter = logging.Formatter("%(message)s")  # Keep console output simple

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File handler (if log_file is specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    _logger_instance = logger
    return _logger_instance
