"""
core/logger.py
──────────────
Centralised logging configuration for the Baxter platform.

All backend modules should import the logger from here:

    from core.logger import logger

The logger writes to **stdout** with structured formatting so every action
is visible in the terminal where the backend server runs.

Format:
    [2024-08-17 11:30:00] [INFO   ] [server] Starting Baxter API server...
    [2024-08-17 11:30:01] [WARNING] [llm_factory] Rate limit hit on key 2

Log levels:
    DEBUG    — verbose internals (hidden by default; set LOG_LEVEL=DEBUG)
    INFO     — normal operations (default)
    WARNING  — recoverable issues, fallbacks triggered
    ERROR    — failures that need attention
    CRITICAL — unrecoverable errors
"""

import logging
import os
import sys


# ── Configuration ────────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "[%(asctime)s] [%(levelname)-7s] [%(module)-14s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── Logger setup ─────────────────────────────────────────────────────────────

def _setup_logger() -> logging.Logger:
    """
    Creates and configures the root 'baxter' logger.

    - Single StreamHandler writing to sys.stdout (visible in the backend terminal).
    - Level controlled by LOG_LEVEL env var (default: INFO).
    - Uses structured format with timestamps, levels, and module names.

    Returns:
        Configured logging.Logger instance.
    """
    _logger = logging.getLogger("baxter")

    # Prevent duplicate handlers if this module is re-imported
    if _logger.handlers:
        return _logger

    _logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    _logger.addHandler(handler)

    # Prevent log messages from propagating to the root logger
    # (avoids duplicate output when uvicorn's own logging is active)
    _logger.propagate = False

    return _logger


logger = _setup_logger()
