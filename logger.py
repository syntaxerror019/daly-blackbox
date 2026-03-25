"""
logger.py - Logging configuration for Daly BMS Black Box
"""

import logging
import logging.handlers
from pathlib import Path
from config import cfg


def setup_logging():
    level = getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO)

    Path(cfg.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        cfg.LOG_FILE,
        maxBytes=cfg.LOG_MAX_BYTES,
        backupCount=cfg.LOG_BACKUP_COUNT
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
