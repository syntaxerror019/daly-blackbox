"""
bms_poller.py - Background thread that continuously polls the Daly BMS
and broadcasts updates via SocketIO.
"""
import logging
import threading
import time
from datetime import datetime, timezone

from config import Config
from database import purge_old_records, save_snapshot

log = logging.getLogger(__name__)

# Global: latest snapshot in memory (thread-safe via lock)
_lock = threading.Lock()
_latest: dict | None = None
_connected: bool = False
_last_error: str | None = None
_last_poll_ts: str | None = None

# Purge runs once per hour
_PURGE_INTERVAL = 3600


def get_latest() -> dict | None:
    with _lock:
        return _latest


def get_status() -> dict:
    with _lock:
        return {
            "connected": _connected,
            "last_error": _last_error,
            "last_poll_ts": _last_poll_ts,
        }


def _update(data: dict | None, error: str | None = None) -> None:
    global _latest, _connected, _last_error, _last_poll_ts
    with _lock:
        if data is not None:
            _latest = data
            _connected = True
            _last_error = None
            _last_poll_ts = datetime.now(timezone.utc).isoformat()
        else:
            _connected = False
            _last_error = error


def polling_loop(socketio) -> None:
    """Main loop — runs in a daemon thread."""
    log.info("BMS poller starting. Port=%s  Interval=%.1fs", Config.BMS_PORT, Config.POLL_INTERVAL)

    try:
        from dalybms import DalyBMS
        bms = DalyBMS()
        bms.connect(Config.BMS_PORT)
        log.info("Connected to BMS on %s", Config.BMS_PORT)
    except Exception as exc:
        log.error("Failed to connect to BMS: %s", exc)
        _update(None, str(exc))
        bms = None

    last_purge = time.monotonic()

    while True:
        loop_start = time.monotonic()

        # --- Purge old records periodically ---
        if time.monotonic() - last_purge > _PURGE_INTERVAL:
            purge_old_records()
            last_purge = time.monotonic()

        # --- Poll BMS ---
        try:
            if bms is None:
                # Retry connection
                from dalybms import DalyBMS
                bms = DalyBMS()
                bms.connect(Config.BMS_PORT)
                log.info("Reconnected to BMS on %s", Config.BMS_PORT)

            data = bms.get_all()

            if data:
                _update(data)
                save_snapshot(data)
                # Broadcast to all connected WebSocket clients
                payload = {"data": data, "ts": _last_poll_ts}
                socketio.emit("bms_update", payload, namespace="/live")
            else:
                _update(None, "BMS returned no data")
                log.warning("BMS returned empty data")

        except Exception as exc:
            log.error("BMS poll error: %s", exc)
            _update(None, str(exc))
            bms = None  # Force reconnect next loop

        # --- Sleep for remainder of interval ---
        elapsed = time.monotonic() - loop_start
        sleep_time = max(0.1, Config.POLL_INTERVAL - elapsed)
        time.sleep(sleep_time)


def start_poller(socketio) -> threading.Thread:
    t = threading.Thread(target=polling_loop, args=(socketio,), daemon=True, name="bms-poller")
    t.start()
    return t
