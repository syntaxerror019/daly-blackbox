"""
config.py - Centralised configuration from .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=False)
load_dotenv(Path(__file__).parent / ".env.example", override=False)


class _Config:
    # BMS
    BMS_SERIAL_PORT: str      = os.getenv("BMS_SERIAL_PORT", "/dev/ttyUSB0")
    BMS_SERIAL_BAUD: int      = int(os.getenv("BMS_SERIAL_BAUD", "9600"))
    BMS_CELL_COUNT: int       = int(os.getenv("BMS_CELL_COUNT", "24"))
    BMS_POLL_INTERVAL: int    = int(os.getenv("BMS_POLL_INTERVAL", "5"))
    BMS_POLL_TIMEOUT: int     = int(os.getenv("BMS_POLL_TIMEOUT", "10"))

    # Data
    DB_PATH: str              = os.getenv("DB_PATH", "data/bms.db")
    RETENTION_DAYS: int       = int(os.getenv("RETENTION_DAYS", "90"))
    RETENTION_CHECK_INTERVAL: int = int(os.getenv("RETENTION_CHECK_INTERVAL", "3600"))

    # Web
    WEB_HOST: str             = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int             = int(os.getenv("WEB_PORT", "5000"))
    WEB_DEBUG: bool           = os.getenv("WEB_DEBUG", "false").lower() == "true"
    SECRET_KEY: str           = os.getenv("SECRET_KEY", "dev-secret-please-change")

    # Auth
    WEB_USERNAME: str         = os.getenv("WEB_USERNAME", "admin")
    WEB_PASSWORD: str         = os.getenv("WEB_PASSWORD", "changeme")

    # Logging
    LOG_LEVEL: str            = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str             = os.getenv("LOG_FILE", "logs/blackbox.log")
    LOG_MAX_BYTES: int        = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    LOG_BACKUP_COUNT: int     = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # Alerts
    ALERT_LOW_SOC: float      = float(os.getenv("ALERT_LOW_SOC", "15"))
    ALERT_HIGH_TEMP: float    = float(os.getenv("ALERT_HIGH_TEMP", "45"))
    ALERT_CELL_VOLTAGE_DIFF: float = float(os.getenv("ALERT_CELL_VOLTAGE_DIFF", "0.1"))


cfg = _Config()
