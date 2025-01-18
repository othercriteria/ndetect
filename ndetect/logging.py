"""Logging configuration for ndetect."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from ndetect.types import JsonDict


class StructuredLogger(logging.Logger):
    """Logger that supports structured logging with fields."""

    def debug_with_fields(self, msg: str, **fields: Any) -> None:
        """Log a debug message with structured fields."""
        if fields:
            msg = f"{msg} {fields}"
        self.debug(msg)

    def info_with_fields(self, msg: str, **fields: Any) -> None:
        """Log a debug message with structured fields (at DEBUG level).

        Note: All structured logging is done at DEBUG level to keep the console clean.
        Use regular info() for user-facing messages.
        """
        if fields:
            msg = f"{msg} {fields}"
        # Log structured data at DEBUG level
        self.debug(msg)

    def warning_with_fields(self, msg: str, **fields: Any) -> None:
        """Log a warning message with structured fields."""
        if fields:
            msg = f"{msg} {fields}"
        self.warning(msg)

    def error_with_fields(self, msg: str, **fields: Any) -> None:
        """Log an error message with structured fields."""
        if fields:
            msg = f"{msg} {fields}"
        self.error(msg)


# Global logger instance
_logger_instance: Optional[StructuredLogger] = None


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


def get_logger() -> StructuredLogger:
    """Get or create the logger instance."""
    global _logger_instance
    if _logger_instance is None:
        # Register our custom logger class
        logging.setLoggerClass(StructuredLogger)

        # Create a basic logger with just stderr output for early logging
        logger = logging.getLogger("ndetect")
        if not isinstance(logger, StructuredLogger):
            raise RuntimeError("Logger instantiation failed")

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            handler.setLevel(logging.INFO)  # Changed from WARNING to INFO
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)  # Changed from WARNING to INFO
        _logger_instance = logger
    assert _logger_instance is not None
    return _logger_instance


def setup_logging(
    log_file: Union[str, Path], verbose: bool = False
) -> StructuredLogger:
    """Set up logging configuration."""
    if log_file is None:
        raise ValueError("log_file cannot be None")

    global _logger_instance
    logger = get_logger()

    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set up file handler for all messages (DEBUG and above)
    file_handler = logging.FileHandler(str(log_file))
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)

    # Set up stream handler for user-facing messages (INFO and above by default)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(
        logging.DEBUG if verbose else logging.INFO
    )  # Changed from WARNING to INFO
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)

    # Set overall logger level to DEBUG to capture all messages
    logger.setLevel(logging.DEBUG)

    _logger_instance = logger
    return logger
