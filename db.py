"""
db.py - Database layer for Daly BMS Black Box
All timestamps stored as UTC in SQLite. Converted to local time on export.
"""

import sqlite3
import json
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

log = logging.getLogger(__name__)


def get_db_path() -> str:
    from config import cfg
    return cfg.DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(get_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    Path(get_db_path()).parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bms_snapshot (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
                total_voltage   REAL,
                current         REAL,
                soc_percent     REAL,
                highest_voltage REAL,
                highest_cell    INTEGER,
                lowest_voltage  REAL,
                lowest_cell     INTEGER,
                highest_temp    REAL,
                highest_temp_sensor INTEGER,
                lowest_temp     REAL,
                lowest_temp_sensor  INTEGER,
                mode            TEXT,
                charge_mosfet   INTEGER,
                discharge_mosfet INTEGER,
                capacity_ah     REAL,
                cells           INTEGER,
                temp_sensors    INTEGER,
                charger_running INTEGER,
                load_running    INTEGER,
                cycles          INTEGER,
                cell_voltages_json  TEXT,
                temperatures_json   TEXT,
                errors_json         TEXT,
                poll_success    INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_snapshot_ts ON bms_snapshot(ts);

            CREATE TABLE IF NOT EXISTS bms_errors (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
                error   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_errors_ts ON bms_errors(ts);
        """)
    log.info("Database initialised at %s", get_db_path())


def insert_snapshot(data: dict):
    soc  = data.get("soc", {}) or {}
    cvr  = data.get("cell_voltage_range", {}) or {}
    tr   = data.get("temperature_range", {}) or {}
    mfet = data.get("mosfet_status", {}) or {}
    st   = data.get("status", {}) or {}
    cvs  = data.get("cell_voltages", {}) or {}
    temps = data.get("temperatures", {}) or {}
    errors = data.get("errors", []) or []

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO bms_snapshot (
                total_voltage, current, soc_percent,
                highest_voltage, highest_cell, lowest_voltage, lowest_cell,
                highest_temp, highest_temp_sensor, lowest_temp, lowest_temp_sensor,
                mode, charge_mosfet, discharge_mosfet, capacity_ah,
                cells, temp_sensors, charger_running, load_running, cycles,
                cell_voltages_json, temperatures_json, errors_json, poll_success
            ) VALUES (?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?, 1)
        """, (
            soc.get("total_voltage"), soc.get("current"), soc.get("soc_percent"),
            cvr.get("highest_voltage"), cvr.get("highest_cell"),
            cvr.get("lowest_voltage"), cvr.get("lowest_cell"),
            tr.get("highest_temperature"), tr.get("highest_sensor"),
            tr.get("lowest_temperature"), tr.get("lowest_sensor"),
            mfet.get("mode"),
            int(bool(mfet.get("charging_mosfet"))),
            int(bool(mfet.get("discharging_mosfet"))),
            mfet.get("capacity_ah"),
            st.get("cells"), st.get("temperature_sensors"),
            int(bool(st.get("charger_running"))),
            int(bool(st.get("load_running"))),
            st.get("cycles"),
            json.dumps(cvs), json.dumps(temps), json.dumps(errors),
        ))

    if errors:
        with get_conn() as conn:
            conn.executemany("INSERT INTO bms_errors (error) VALUES (?)",
                             [(e,) for e in errors])


def insert_failed_poll():
    with get_conn() as conn:
        conn.execute("INSERT INTO bms_snapshot (poll_success) VALUES (0)")


def get_latest() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM bms_snapshot
            WHERE poll_success = 1
            ORDER BY ts DESC LIMIT 1
        """).fetchone()
    return _row_to_dict(row) if row else None


def get_snapshots(start: datetime, end: datetime, max_points: int = 1000) -> list:
    with get_conn() as conn:
        total = conn.execute("""
            SELECT COUNT(*) FROM bms_snapshot
            WHERE ts BETWEEN ? AND ? AND poll_success = 1
        """, (_fmt(start), _fmt(end))).fetchone()[0]

        if total == 0:
            return []

        step = max(1, total // max_points)
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (ORDER BY ts) AS rn
                FROM bms_snapshot
                WHERE ts BETWEEN ? AND ? AND poll_success = 1
            ) WHERE rn % ? = 0 OR rn = 1
            ORDER BY ts ASC
        """, (_fmt(start), _fmt(end), step)).fetchall()

    return [_row_to_dict(r) for r in rows]


def get_errors(start: datetime, end: datetime) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ts, error FROM bms_errors
            WHERE ts BETWEEN ? AND ?
            ORDER BY ts DESC
        """, (_fmt(start), _fmt(end))).fetchall()
    return [{"ts": r["ts"], "error": r["error"]} for r in rows]


def get_stats(start: datetime, end: datetime) -> dict:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                MIN(soc_percent)     AS min_soc,
                MAX(soc_percent)     AS max_soc,
                AVG(soc_percent)     AS avg_soc,
                MIN(total_voltage)   AS min_voltage,
                MAX(total_voltage)   AS max_voltage,
                AVG(total_voltage)   AS avg_voltage,
                MIN(current)         AS min_current,
                MAX(current)         AS max_current,
                AVG(current)         AS avg_current,
                MIN(lowest_voltage)  AS min_cell_v,
                MAX(highest_voltage) AS max_cell_v,
                MIN(lowest_temp)     AS min_temp,
                MAX(highest_temp)    AS max_temp,
                COUNT(*)             AS samples
            FROM bms_snapshot
            WHERE ts BETWEEN ? AND ? AND poll_success = 1
        """, (_fmt(start), _fmt(end))).fetchone()
    return dict(row) if row else {}


def purge_old_records(retention_days: int):
    if retention_days <= 0:
        return
    cutoff = _fmt(datetime.utcnow() - timedelta(days=retention_days))
    with get_conn() as conn:
        n1 = conn.execute("DELETE FROM bms_snapshot WHERE ts < ?", (cutoff,)).rowcount
        n2 = conn.execute("DELETE FROM bms_errors   WHERE ts < ?", (cutoff,)).rowcount
    log.info("Retention purge: removed %d snapshots, %d error records", n1, n2)


def export_csv(start: datetime, end: datetime, tz_offset_minutes: int = 0) -> str:
    """
    Export snapshots as CSV.
    tz_offset_minutes: client's UTC offset in minutes (e.g. -300 = UTC-5).
    Timestamps in output are converted to local time.
    """
    rows = get_snapshots(start, end, max_points=999999)
    if not rows:
        return "No data in selected range.\n"

    tz = timezone(timedelta(minutes=-tz_offset_minutes))  # JS gives negative for west

    buf = io.StringIO()
    writer = None
    for row in rows:
        cvs  = row.pop("cell_voltages", {}) or {}
        temps_d = row.pop("temperatures", {}) or {}
        row.pop("errors", None)
        row.pop("rn", None)

        # Convert UTC timestamp to local
        ts_str = row.get("ts", "")
        try:
            ts_utc = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts_utc.tzinfo is None:
                ts_utc = ts_utc.replace(tzinfo=timezone.utc)
            row["ts"] = ts_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        for i, v in sorted(cvs.items(), key=lambda x: int(x[0])):
            row[f"cell_{i}_v"] = v
        for i, t in sorted(temps_d.items(), key=lambda x: int(x[0])):
            row[f"temp_{i}_c"] = t

        if writer is None:
            writer = csv.DictWriter(buf, fieldnames=list(row.keys()))
            writer.writeheader()
        writer.writerow(row)

    return buf.getvalue()


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _row_to_dict(row) -> dict:
    d = dict(row)
    for key in ("cell_voltages_json", "temperatures_json", "errors_json"):
        raw = d.pop(key, None)
        short = key.replace("_json", "")
        try:
            d[short] = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            d[short] = {}
    return d
