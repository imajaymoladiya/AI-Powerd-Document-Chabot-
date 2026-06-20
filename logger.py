"""
logger.py
---------
Production-style logging for the whole app. Every module calls get_logger(name)
and writes to the same rotating log files under ./logs :

    logs/app.log     - everything (INFO and above), rotated at ~2 MB x 5 files
    logs/error.log   - errors only (ERROR and above), rotated at ~1 MB x 5 files

Logs also go to the console. Configuration happens once (idempotent).
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

APP_LOG = os.path.join(LOG_DIR, "app.log")
ERROR_LOG = os.path.join(LOG_DIR, "error.log")

_configured = False


def get_logger(name):
    global _configured
    if not _configured:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        # All activity -> logs/app.log
        app_handler = RotatingFileHandler(
            APP_LOG, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(fmt)
        root.addHandler(app_handler)

        # Errors -> logs/error.log
        error_handler = RotatingFileHandler(
            ERROR_LOG, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(fmt)
        root.addHandler(error_handler)

        # Console
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(fmt)
        root.addHandler(console)

        _configured = True

    return logging.getLogger(name)
