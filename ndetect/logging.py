"""Logging configuration for ndetect."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(log_file: Optional[Path] = None, verbose: bool = False) -> None:
    """
    Configure logging for ndetect.

    Args:
        log_file: Optional path to log file. If None, only log to console.
        verbose: If True, set log level to DEBUG.
    """
    # Create logger
    logger = logging.getLogger("ndetect")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Create formatters
    console_formatter = logging.Formatter("%(message)s")
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File handler (if log_file is specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
