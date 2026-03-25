# 🔋 Daly BMS Black Box

A professional, production-ready data logger and web dashboard for Daly BMS units. Designed for LiFePO₄ battery packs (golf carts, EVs, solar storage, etc.).

## Features

- **Real-time polling** via UART serial — configurable interval (default 5 seconds)
- **SQLite database** with automatic data retention and WAL-mode performance
- **Live dashboard** — SOC ring, cell voltage grid, MOSFET status, live charts
- **History & analytics** — time-range selector (1h → 90d), aggregate stats
- **Fault log** — timestamped BMS error history
- **Data export** — CSV and JSON downloads, filterable by date range
- **Secure web UI** — username/password login via session auth
- **Configurable via `.env`** — no code changes needed for deployment

## Hardware

Tested with:
- Daly BMS (UART/RS485 variant)
- 24S LiFePO₄ cells (configurable for any cell count)
- Raspberry Pi / any Linux SBC with a USB-serial adapter

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo>
cd daly-blackbox
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
nano .env
```

Key settings to change:
- `BMS_SERIAL_PORT` — your USB serial port (e.g. `/dev/ttyUSB0`)
- `BMS_CELL_COUNT` — number of cells in series
- `WEB_PASSWORD` — **change this!**
- `SECRET_KEY` — set a long random string

### 3. Run

```bash
python main.py
```

Then open `http://<your-device-ip>:5000` in a browser.

### 4. Run as a service (systemd)

Create `/etc/systemd/system/bms-blackbox.service`:

```ini
[Unit]
Description=Daly BMS Black Box
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/daly-blackbox
ExecStart=/usr/bin/python3 /home/pi/daly-blackbox/main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable bms-blackbox
sudo systemctl start bms-blackbox
sudo journalctl -u bms-blackbox -f
```

## Configuration Reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `BMS_SERIAL_PORT` | `/dev/ttyUSB0` | Serial device path |
| `BMS_SERIAL_BAUD` | `9600` | Baud rate |
| `BMS_CELL_COUNT` | `24` | Cells in series (display only) |
| `BMS_POLL_INTERVAL` | `5` | Seconds between polls |
| `BMS_POLL_TIMEOUT` | `10` | Serial timeout per poll |
| `DB_PATH` | `data/bms.db` | SQLite database path |
| `RETENTION_DAYS` | `90` | Days to keep records (0 = forever) |
| `WEB_HOST` | `0.0.0.0` | Flask bind address |
| `WEB_PORT` | `5000` | HTTP port |
| `WEB_DEBUG` | `false` | Flask debug mode |
| `SECRET_KEY` | *(change me)* | Session signing key |
| `WEB_USERNAME` | `admin` | Login username |
| `WEB_PASSWORD` | `changeme` | Login password |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ALERT_LOW_SOC` | `15` | SOC % for low battery warning |
| `ALERT_HIGH_TEMP` | `45` | Temperature alert threshold (°C) |
| `ALERT_CELL_VOLTAGE_DIFF` | `0.1` | Max cell delta before warning |

## API Endpoints

All endpoints require login session except `/api/health`.

| Endpoint | Description |
|---|---|
| `GET /api/live` | Current in-memory BMS snapshot |
| `GET /api/snapshots?range=24h` | Time-series data for charts |
| `GET /api/stats?range=7d` | Aggregate min/max/avg stats |
| `GET /api/errors?range=24h` | Fault log entries |
| `GET /api/health` | Poll daemon health (no auth) |
| `GET /download/csv?range=7d` | Download CSV export |
| `GET /download/json?range=7d` | Download JSON export |

Range values: `1h`, `6h`, `12h`, `24h`, `7d`, `30d`, `90d`  
Custom range: `?start=2025-01-01T00:00&end=2025-01-07T23:59`

## Project Structure

```
daly-blackbox/
├── main.py          # Entry point — starts scheduler + Flask
├── app.py           # Flask routes and API
├── poller.py        # BMS polling daemon (APScheduler)
├── db.py            # SQLite database layer
├── config.py        # .env configuration
├── logger.py        # Logging setup
├── requirements.txt
├── .env.example     # Config template
├── .env             # Your config (gitignored)
├── data/            # SQLite database
├── logs/            # Rotating log files
└── templates/
    ├── base.html    # Layout, sidebar, nav
    ├── login.html   # Login page
    ├── dashboard.html # Live dashboard
    └── history.html   # History & analytics
```

## License

MIT
