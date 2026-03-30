"""
app.py - Flask + SocketIO BMS Monitor Application
"""
import csv
import io
import json
import logging
import logging.handlers
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_socketio import SocketIO, emit

import bms_poller
from config import Config
from database import init_db, query_snapshots, query_snapshots_paginated

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(Config.LOG_FILE) or ".", exist_ok=True)

_log_handlers = [
    logging.StreamHandler(),
    logging.handlers.RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
    ),
]
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_log_handlers,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == Config.WEB_USERNAME and password == Config.WEB_PASSWORD:
            session["logged_in"] = True
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        error = "Invalid credentials"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Main pages
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", config=Config)


@app.route("/history")
@login_required
def history():
    return render_template("history.html", config=Config)


@app.route("/hud")
@login_required
def hud():
    """Driver HUD — optimised for small bright displays."""
    return render_template("hud.html", config=Config)


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.route("/api/status")
@login_required
def api_status():
    status = bms_poller.get_status()
    latest = bms_poller.get_latest()
    return jsonify({"poller": status, "latest": latest})


@app.route("/api/latest")
@login_required
def api_latest():
    data = bms_poller.get_latest()
    if data is None:
        return jsonify({"error": "No data yet"}), 503
    return jsonify({"data": data, "ts": bms_poller.get_status()["last_poll_ts"]})


def _parse_timeframe() -> tuple[datetime, datetime]:
    """Parse ?start= and ?end= query params. Defaults to last 24h."""
    now = datetime.now(timezone.utc)
    try:
        end = datetime.fromisoformat(request.args["end"]) if "end" in request.args else now
        if "start" in request.args:
            start = datetime.fromisoformat(request.args["start"])
        else:
            hours = float(request.args.get("hours", 24))
            start = now - timedelta(hours=hours)
    except (ValueError, KeyError):
        start = now - timedelta(hours=24)
        end = now
    return start, end


@app.route("/api/history")
@login_required
def api_history():
    start, end = _parse_timeframe()
    limit = int(request.args.get("limit", 2000))
    rows = query_snapshots_paginated(start, end, limit=limit)
    return jsonify({"count": len(rows), "start": start.isoformat(), "end": end.isoformat(), "rows": rows})


@app.route("/api/download/csv")
@login_required
def api_download_csv():
    start, end = _parse_timeframe()
    rows = query_snapshots(start, end)

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        # Header
        writer.writerow([
            "timestamp", "total_voltage", "current", "soc_percent",
            "highest_cell_v", "lowest_cell_v", "cell_delta_v",
            "temp_high", "temp_low", "cycles", "capacity_ah",
            "mosfet_mode", "charging_mosfet", "discharging_mosfet",
            "charger_running", "load_running", "errors",
        ])
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)

        for r in rows:
            cvr = r.get("cell_voltage_range", {})
            tr = r.get("temperature_range", {})
            ms = r.get("mosfet", {})
            st = r.get("status", {})
            s = r.get("soc", {})
            writer.writerow([
                r["ts"],
                s.get("total_voltage"), s.get("current"), s.get("soc_percent"),
                cvr.get("highest_voltage"), cvr.get("lowest_voltage"),
                round((cvr.get("highest_voltage") or 0) - (cvr.get("lowest_voltage") or 0), 4),
                tr.get("highest_temperature"), tr.get("lowest_temperature"),
                st.get("cycles"), ms.get("capacity_ah"),
                ms.get("mode"), ms.get("charging"), ms.get("discharging"),
                st.get("charger_running"), st.get("load_running"),
                "; ".join(r.get("errors", [])),
            ])
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    fname = f"bms_{start.strftime('%Y%m%d_%H%M')}_{end.strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@app.route("/api/download/json")
@login_required
def api_download_json():
    start, end = _parse_timeframe()
    rows = query_snapshots(start, end)
    out = json.dumps({"start": start.isoformat(), "end": end.isoformat(), "rows": rows}, indent=2)
    fname = f"bms_{start.strftime('%Y%m%d_%H%M')}_{end.strftime('%Y%m%d_%H%M')}.json"
    return Response(
        out,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# ---------------------------------------------------------------------------
# SocketIO namespace
# ---------------------------------------------------------------------------

@socketio.on("connect", namespace="/live")
def ws_connect():
    if not session.get("logged_in"):
        return False  # Reject unauthenticated
    # Send latest immediately on connect
    data = bms_poller.get_latest()
    if data:
        emit("bms_update", {"data": data, "ts": bms_poller.get_status()["last_poll_ts"]})
    log.debug("WebSocket client connected")


@socketio.on("disconnect", namespace="/live")
def ws_disconnect():
    log.debug("WebSocket client disconnected")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def create_app():
    init_db()
    bms_poller.start_poller(socketio)
    return app


if __name__ == "__main__":
    create_app()
    log.info("Starting BMS Monitor on %s:%d", Config.WEB_HOST, Config.WEB_PORT)
    socketio.run(app, host=Config.WEB_HOST, port=Config.WEB_PORT, debug=False)
