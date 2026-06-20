"""
logger.py
---------
Production-style logging for the whole app. Every module calls get_logger(name)
and writes to rotating log files:

    logs/app.log     - everything (INFO and above), rotated at ~2 MB x 5 files
    logs/error.log   - errors only (ERROR and above), rotated at ~1 MB x 5 files

Logs also go to the console. Configuration happens once (idempotent).

On hosts with a read-only filesystem (e.g. serverless), file logging is skipped
gracefully and only console logging is used -- the app never crashes just because
it cannot create the logs folder. Override the folder with the LOG_DIR env var.
"""

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler

LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))

_configured = False


def _pick_log_dir():
    """Return the first writable log directory, or None if none is writable."""
    candidates = [LOG_DIR, os.path.join(tempfile.gettempdir(), "document_agent_logs")]
    for directory in candidates:
        try:
            os.makedirs(directory, exist_ok=True)
            probe = os.path.join(directory, ".write_test")
            with open(probe, "w") as handle:
                handle.write("ok")
            os.remove(probe)
            return directory
        except Exception:
            continue
    return None


def get_logger(name):
    global _configured
    if not _configured:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        # Console always works.
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(fmt)
        root.addHandler(console)

        # File logging only if we have a writable directory.
        log_dir = _pick_log_dir()
        if log_dir:
            app_handler = RotatingFileHandler(
                os.path.join(log_dir, "app.log"),
                maxBytes=2_000_000, backupCount=5, encoding="utf-8",
            )
            app_handler.setLevel(logging.INFO)
            app_handler.setFormatter(fmt)
            root.addHandler(app_handler)

            error_handler = RotatingFileHandler(
                os.path.join(log_dir, "error.log"),
                maxBytes=1_000_000, backupCount=5, encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(fmt)
            root.addHandler(error_handler)
        else:
            root.warning("No writable log directory; logging to console only.")

        _configured = True

    return logging.getLogger(name)
