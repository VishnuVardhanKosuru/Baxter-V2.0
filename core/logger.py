"""
core/logger.py
──────────────
Centralised logging configuration for the Baxter platform.

All backend modules should import the logger from here:

    from core.logger import logger

Writes to stdout, and additionally to logs/baxter.log when LOG_TO_FILE=true.

Format:
    [2024-08-17 11:30:00] [INFO   ] [server] Starting Baxter API server...
    [2024-08-17 11:30:01] [WARNING] [llm_factory] Rate limit hit on key 2

Log levels (LOG_LEVEL env var, default INFO):
    DEBUG    — verbose internals
    INFO     — normal operations
    WARNING  — recoverable issues, fallbacks triggered
    ERROR    — failures that need attention
    CRITICAL — unrecoverable errors
"""

import logging
import sys

from core import constants as const


def _setup_logger() -> logging.Logger:
    """
    Creates and configures the root 'baxter' logger.

    Handlers: stdout always; a rotating file handler when LOG_TO_FILE=true.
    Never raises — if the log directory cannot be created, file logging is
    skipped and stdout logging still works.
    """
    _logger = logging.getLogger("baxter")

    # Prevent duplicate handlers if this module is re-imported
    if _logger.handlers:
        return _logger

    level = getattr(logging, const.LOG_LEVEL, logging.INFO)
    _logger.setLevel(level)
    formatter = logging.Formatter(const.LOG_FORMAT, datefmt=const.LOG_DATE_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    _logger.addHandler(stream_handler)

    if const.LOG_TO_FILE:
        try:
            from logging.handlers import RotatingFileHandler

            const.DIR_LOGS.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                const.LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            _logger.addHandler(file_handler)
        except OSError as exc:
            _logger.warning("File logging disabled — cannot write %s: %s", const.LOG_FILE, exc)

    # Prevent propagation to the root logger (avoids duplicate output when
    # uvicorn's own logging is active).
    _logger.propagate = False

    return _logger


logger = _setup_logger()
