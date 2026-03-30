"""
config.py - Load all configuration from .env
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # BMS
    BMS_PORT: str = os.getenv("BMS_PORT", "/dev/ttyUSB0")
    BMS_CELL_COUNT: int = int(os.getenv("BMS_CELL_COUNT", "24"))

    # Polling
    POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "2"))

    # Web
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change_me")

    # Auth
    WEB_USERNAME: str = os.getenv("WEB_USERNAME", "admin")
    WEB_PASSWORD: str = os.getenv("WEB_PASSWORD", "admin")

    # Data retention
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "90"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/bms_monitor.log")
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # Alerts
    CELL_VOLTAGE_MIN_WARN: float = float(os.getenv("CELL_VOLTAGE_MIN_WARN", "3.0"))
    CELL_VOLTAGE_MAX_WARN: float = float(os.getenv("CELL_VOLTAGE_MAX_WARN", "3.65"))
    TEMP_MAX_WARN: float = float(os.getenv("TEMP_MAX_WARN", "45"))
    SOC_MIN_WARN: float = float(os.getenv("SOC_MIN_WARN", "10"))

    # SQLite DB path
    DB_PATH: str = os.getenv("DB_PATH", "data/bms_log.db")
