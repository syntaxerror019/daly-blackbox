"""
database.py - SQLAlchemy ORM models and database utilities
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import Config

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class BMSSnapshot(Base):
    """One complete BMS poll snapshot."""

    __tablename__ = "bms_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)

    # SOC
    total_voltage = Column(Float)
    current = Column(Float)
    soc_percent = Column(Float)

    # Cell voltage range
    highest_voltage = Column(Float)
    highest_cell = Column(Integer)
    lowest_voltage = Column(Float)
    lowest_cell = Column(Integer)

    # Temperature range
    highest_temperature = Column(Float)
    highest_sensor = Column(Integer)
    lowest_temperature = Column(Float)
    lowest_sensor = Column(Integer)

    # MOSFET
    mosfet_mode = Column(String(32))
    charging_mosfet = Column(Integer)  # 0/1
    discharging_mosfet = Column(Integer)  # 0/1
    capacity_ah = Column(Float)

    # Status
    cells = Column(Integer)
    temperature_sensors = Column(Integer)
    charger_running = Column(Integer)
    load_running = Column(Integer)
    cycles = Column(Integer)

    # Per-cell voltages JSON: {"1": 3.72, ...}
    cell_voltages_json = Column(Text)
    # Temperatures JSON: {"1": 15, ...}
    temperatures_json = Column(Text)
    # Errors JSON list
    errors_json = Column(Text)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts.isoformat(),
            "soc": {
                "total_voltage": self.total_voltage,
                "current": self.current,
                "soc_percent": self.soc_percent,
            },
            "cell_voltage_range": {
                "highest_voltage": self.highest_voltage,
                "highest_cell": self.highest_cell,
                "lowest_voltage": self.lowest_voltage,
                "lowest_cell": self.lowest_cell,
            },
            "temperature_range": {
                "highest_temperature": self.highest_temperature,
                "highest_sensor": self.highest_sensor,
                "lowest_temperature": self.lowest_temperature,
                "lowest_sensor": self.lowest_sensor,
            },
            "mosfet": {
                "mode": self.mosfet_mode,
                "charging": bool(self.charging_mosfet),
                "discharging": bool(self.discharging_mosfet),
                "capacity_ah": self.capacity_ah,
            },
            "status": {
                "cells": self.cells,
                "temperature_sensors": self.temperature_sensors,
                "charger_running": bool(self.charger_running),
                "load_running": bool(self.load_running),
                "cycles": self.cycles,
            },
            "cell_voltages": json.loads(self.cell_voltages_json or "{}"),
            "temperatures": json.loads(self.temperatures_json or "{}"),
            "errors": json.loads(self.errors_json or "[]"),
        }


_engine = None
_Session = None


def init_db() -> None:
    global _engine, _Session
    import os

    os.makedirs(os.path.dirname(Config.DB_PATH) or ".", exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{Config.DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine)
    log.info("Database initialised at %s", Config.DB_PATH)


def get_session() -> Session:
    if _Session is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _Session()


def save_snapshot(data: dict) -> None:
    """Persist a full BMS data dict to the database."""
    try:
        with get_session() as session:
            snap = BMSSnapshot(
                ts=datetime.now(timezone.utc),
                total_voltage=data.get("soc", {}).get("total_voltage"),
                current=data.get("soc", {}).get("current"),
                soc_percent=data.get("soc", {}).get("soc_percent"),
                highest_voltage=data.get("cell_voltage_range", {}).get("highest_voltage"),
                highest_cell=data.get("cell_voltage_range", {}).get("highest_cell"),
                lowest_voltage=data.get("cell_voltage_range", {}).get("lowest_voltage"),
                lowest_cell=data.get("cell_voltage_range", {}).get("lowest_cell"),
                highest_temperature=data.get("temperature_range", {}).get("highest_temperature"),
                highest_sensor=data.get("temperature_range", {}).get("highest_sensor"),
                lowest_temperature=data.get("temperature_range", {}).get("lowest_temperature"),
                lowest_sensor=data.get("temperature_range", {}).get("lowest_sensor"),
                mosfet_mode=data.get("mosfet_status", {}).get("mode"),
                charging_mosfet=int(data.get("mosfet_status", {}).get("charging_mosfet", False)),
                discharging_mosfet=int(data.get("mosfet_status", {}).get("discharging_mosfet", False)),
                capacity_ah=data.get("mosfet_status", {}).get("capacity_ah"),
                cells=data.get("status", {}).get("cells"),
                temperature_sensors=data.get("status", {}).get("temperature_sensors"),
                charger_running=int(data.get("status", {}).get("charger_running", False)),
                load_running=int(data.get("status", {}).get("load_running", False)),
                cycles=data.get("status", {}).get("cycles"),
                cell_voltages_json=json.dumps(data.get("cell_voltages", {})),
                temperatures_json=json.dumps(data.get("temperatures", {})),
                errors_json=json.dumps(data.get("errors", [])),
            )
            session.add(snap)
            session.commit()
    except Exception as exc:
        log.error("Failed to save snapshot: %s", exc)


def purge_old_records() -> int:
    """Delete records older than DATA_RETENTION_DAYS. Returns number deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=Config.DATA_RETENTION_DAYS)
    try:
        with get_session() as session:
            deleted = (
                session.query(BMSSnapshot)
                .filter(BMSSnapshot.ts < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            if deleted:
                log.info("Purged %d old records (retention: %d days)", deleted, Config.DATA_RETENTION_DAYS)
            return deleted
    except Exception as exc:
        log.error("Failed to purge old records: %s", exc)
        return 0


def query_snapshots(start: datetime, end: datetime) -> list[dict]:
    """Return snapshots between start and end as list of dicts."""
    with get_session() as session:
        rows = (
            session.query(BMSSnapshot)
            .filter(BMSSnapshot.ts >= start, BMSSnapshot.ts <= end)
            .order_by(BMSSnapshot.ts.asc())
            .all()
        )
        return [r.to_dict() for r in rows]


def query_snapshots_paginated(start: datetime, end: datetime, limit: int = 5000) -> list[dict]:
    """Return up to `limit` snapshots, evenly sampled across the time range."""
    with get_session() as session:
        total = (
            session.query(BMSSnapshot)
            .filter(BMSSnapshot.ts >= start, BMSSnapshot.ts <= end)
            .count()
        )
        if total == 0:
            return []
        step = max(1, total // limit)
        # Use row_number trick via SQLite
        rows = (
            session.query(BMSSnapshot)
            .filter(BMSSnapshot.ts >= start, BMSSnapshot.ts <= end)
            .order_by(BMSSnapshot.ts.asc())
            .all()
        )
        sampled = rows[::step]
        return [r.to_dict() for r in sampled]
