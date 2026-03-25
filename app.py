"""
app.py - Flask + SocketIO web application for Daly BMS Black Box
"""

import json
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, redirect, url_for, request,
                   session, jsonify, Response)
from flask_socketio import SocketIO, disconnect

from config import cfg
import db
import poller

log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = cfg.SECRET_KEY

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Hand socketio to poller so it can broadcast after each poll
poller.set_socketio(socketio)


# ── Auth ───────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def _parse_range(preset=None, start=None, end=None):
    now = datetime.utcnow()
    presets = {
        "5m":  (now - timedelta(minutes=5),  now, "Last 5 minutes"),
        "15m": (now - timedelta(minutes=15), now, "Last 15 minutes"),
        "1h":  (now - timedelta(hours=1),    now, "Last 1 hour"),
        "6h":  (now - timedelta(hours=6),    now, "Last 6 hours"),
        "12h": (now - timedelta(hours=12),   now, "Last 12 hours"),
        "24h": (now - timedelta(hours=24),   now, "Last 24 hours"),
        "7d":  (now - timedelta(days=7),     now, "Last 7 days"),
        "30d": (now - timedelta(days=30),    now, "Last 30 days"),
        "90d": (now - timedelta(days=90),    now, "Last 90 days"),
        "all": (datetime(2000, 1, 1),        now, "All time"),
    }
    if preset and preset in presets:
        return presets[preset]
    try:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        return s, e, f"{s.strftime('%b %d %H:%M')} \u2192 {e.strftime('%b %d %H:%M')}"
    except Exception:
        return presets["24h"]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (request.form.get("username") == cfg.WEB_USERNAME and
                request.form.get("password") == cfg.WEB_PASSWORD):
            session["logged_in"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Invalid credentials"
    return render_template("login.html", error=error, config=cfg)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", live=poller.get_live_data(), cfg=cfg)


@app.route("/history")
@login_required
def history():
    preset = request.args.get("range", "24h")
    s, e, label = _parse_range(preset, request.args.get("start"), request.args.get("end"))
    return render_template("history.html",
                           stats=db.get_stats(s, e),
                           errors=db.get_errors(s, e),
                           range_label=label, preset=preset,
                           range_start=s.isoformat(), range_end=e.isoformat(),
                           cfg=cfg)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/live")
@login_required
def api_live():
    return jsonify(poller.get_live_data())


@app.route("/api/snapshots")
@login_required
def api_snapshots():
    preset  = request.args.get("range", "24h")
    max_pts = int(request.args.get("max_points", 500))
    s, e, label = _parse_range(preset, request.args.get("start"), request.args.get("end"))
    rows = db.get_snapshots(s, e, max_points=max_pts)
    return jsonify({"label": label, "start": s.isoformat(), "end": e.isoformat(),
                    "count": len(rows), "rows": rows})


@app.route("/api/stats")
@login_required
def api_stats():
    s, e, label = _parse_range(request.args.get("range", "24h"),
                                request.args.get("start"), request.args.get("end"))
    return jsonify({"label": label, **db.get_stats(s, e)})


@app.route("/api/errors")
@login_required
def api_errors():
    s, e, _ = _parse_range(request.args.get("range", "24h"),
                            request.args.get("start"), request.args.get("end"))
    return jsonify(db.get_errors(s, e))


@app.route("/api/health")
def health():
    live = poller.get_live_data()
    return jsonify({"status": "ok" if live["ok"] else "degraded",
                    "last_poll": live["ts"],
                    "poll_count": live["poll_count"],
                    "fail_count": live["fail_count"]})


# ── Download CSV only ─────────────────────────────────────────────────────────

@app.route("/download/csv")
@login_required
def download_csv():
    preset = request.args.get("range", "24h")
    s, e, _ = _parse_range(preset, request.args.get("start"), request.args.get("end"))
    tz_offset = int(request.args.get("tz_offset", 0))  # minutes, from JS
    csv_data = db.export_csv(s, e, tz_offset_minutes=tz_offset)
    if preset == "all":
        fname = "bms_all_time.csv"
    else:
        fname = f"bms_{s.strftime('%Y%m%d_%H%M')}_{e.strftime('%Y%m%d_%H%M')}.csv"
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})


# ── WebSocket ─────────────────────────────────────────────────────────────────

@socketio.on("connect", namespace="/live")
def ws_connect():
    if not session.get("logged_in"):
        disconnect()
        return
    log.debug("WS client connected")
    # Send latest data immediately on connect
    socketio.emit("bms_update", poller.get_live_data(), namespace="/live", to=request.sid)


@socketio.on("disconnect", namespace="/live")
def ws_disconnect():
    log.debug("WS client disconnected")
