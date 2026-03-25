"""
poller.py - Background BMS polling daemon
Reads all data from the Daly BMS over UART and stores to DB.
Runs as an APScheduler job alongside the Flask app.
Broadcasts live data over WebSocket after every successful poll.
"""

import logging
import threading
from datetime import datetime
from typing import Optional

from config import cfg
import db

log = logging.getLogger(__name__)

_lock = threading.Lock()
_latest_data: Optional[dict] = None
_last_poll_ts: Optional[datetime] = None
_last_poll_ok: bool = False
_poll_count: int = 0
_fail_count: int = 0

# Set by main.py after socketio is created
_socketio = None

def set_socketio(sio):
    global _socketio
    _socketio = sio


def get_live_data() -> dict:
    with _lock:
        return {
            "data": _latest_data,
            "ts": _last_poll_ts.isoformat() if _last_poll_ts else None,
            "ok": _last_poll_ok,
            "poll_count": _poll_count,
            "fail_count": _fail_count,
        }


def poll_bms():
    global _latest_data, _last_poll_ts, _last_poll_ok, _poll_count, _fail_count

    log.debug("Polling BMS on %s …", cfg.BMS_SERIAL_PORT)

    try:
        from dalybms import DalyBMS
        bms = DalyBMS(request_retries=3)
        bms.connect(cfg.BMS_SERIAL_PORT)

        data = bms.get_all()
        bms.disconnect()

        if not data:
            raise ValueError("BMS returned empty data")

        db.insert_snapshot(data)

        with _lock:
            _latest_data = data
            _last_poll_ts = datetime.utcnow()
            _last_poll_ok = True
            _poll_count += 1

        log.debug("Poll #%d OK — SOC %.1f%% @ %.2fV",
                  _poll_count,
                  (data.get("soc") or {}).get("soc_percent", 0),
                  (data.get("soc") or {}).get("total_voltage", 0))

        # Push to all connected WebSocket clients
        if _socketio:
            payload = get_live_data()
            _socketio.emit("bms_update", payload, namespace="/live")

    except Exception as exc:
        db.insert_failed_poll()
        with _lock:
            _last_poll_ts = datetime.utcnow()
            _last_poll_ok = False
            _fail_count += 1
        log.warning("Poll failed (%s): %s", type(exc).__name__, exc)

        if _socketio:
            _socketio.emit("bms_error", {"msg": str(exc)}, namespace="/live")


def run_retention():
    log.info("Running data retention cleanup …")
    db.purge_old_records(cfg.RETENTION_DAYS)
