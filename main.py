"""
main.py - Entry point for Daly BMS Black Box
"""

import logging
from logger import setup_logging
setup_logging()

log = logging.getLogger(__name__)

from config import cfg
import db
from poller import poll_bms, run_retention
from app import app, socketio

from apscheduler.schedulers.background import BackgroundScheduler


def main():
    log.info("=" * 60)
    log.info("  Daly BMS Black Box starting up")
    log.info("  BMS port : %s", cfg.BMS_SERIAL_PORT)
    log.info("  Poll interval : %ds", cfg.BMS_POLL_INTERVAL)
    log.info("  Web : http://%s:%d", cfg.WEB_HOST, cfg.WEB_PORT)
    log.info("=" * 60)

    db.init_db()

    log.info("Running initial BMS poll …")
    poll_bms()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(poll_bms, "interval", seconds=cfg.BMS_POLL_INTERVAL,
                      id="poll_bms", max_instances=1,
                      misfire_grace_time=cfg.BMS_POLL_INTERVAL * 2)
    scheduler.add_job(run_retention, "interval", seconds=cfg.RETENTION_CHECK_INTERVAL,
                      id="retention", max_instances=1)
    scheduler.start()
    log.info("Scheduler started")

    socketio.run(app,
                 host=cfg.WEB_HOST,
                 port=cfg.WEB_PORT,
                 debug=cfg.WEB_DEBUG,
                 use_reloader=False,
                 allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
