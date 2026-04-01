# Daly BMS Monitor

A professional, production-ready black box data logger and web dashboard for the **Daly BMS** via UART.

## Features

- **Real-time dashboard** — live SOC, voltage, current, temperature, per-cell bars, MOSFET status, error alerts
- **WebSocket live updates** — sub-second chart refresh via Socket.IO
- **Driver HUD** — dedicated full-screen display optimised for small screens in direct sunlight (high-contrast yellow/white on dark navy)
- **History page** — browse any time range (1h → 30d → custom), with zoomable charts
- **CSV & JSON export** — download any time range with one click
- **SQLite logging** — lightweight, zero-config persistent storage
- **Configurable retention** — automatically purge old records
- **Single `.env` config** — port, auth, polling interval, retention, alerts all in one place
- **Systemd service** — runs as a reliable background daemon

---

## Quick Start

### 1. Clone / copy project

```bash
git clone <bestest repo evr frfr (put the url)> /opt/daly-bms-monitor
cd /opt/daly-bms-monitor
```

### 2. Create virtual environment & install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

Edit `.env`:

```env
BMS_PORT=/dev/ttyUSB0     # Your serial port
WEB_PASSWORD=your_password
POLL_INTERVAL=2            # seconds between polls
DATA_RETENTION_DAYS=90
```

### 4. Run

```bash
python app.py
```

Visit `http://<your-ip>:8000`

### 5. (Optional) Install as systemd service

```bash
# Edit bms-monitor.service — set User= and WorkingDirectory= to match your setup
sudo cp bms-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bms-monitor
sudo journalctl -u bms-monitor -f   # view logs
```

---

## Pages

| URL | Description |
|-----|-------------|
| `/` | Live dashboard |
| `/history` | Historical charts + CSV/JSON export |
| `/hud` | Driver HUD (open in full-screen on dash display) |
| `/login` | Authentication |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/latest` | Latest BMS snapshot (JSON) |
| `GET /api/history?hours=24` | Historical data (sampled, max 2000 points) |
| `GET /api/download/csv?hours=24` | Download CSV for time range |
| `GET /api/download/json?hours=24` | Download JSON for time range |

All time-range endpoints accept `?start=<ISO>&end=<ISO>` or `?hours=<n>`.

---

## Hardware Setup

```
LiFePO4 Cells (24S)
        │
   Daly BMS
        │ UART (TX/RX)
   USB-UART adapter (e.g. CH340, CP2102)
        │ /dev/ttyUSB0
   Raspberry Pi / SBC
        │
   BMS Monitor (this project)
```

Default UART settings: **9600 baud, 8N1** (handled automatically by `python-daly-bms`).

---

## Configuration Reference (`.env`)

| Key | Default | Description |
|-----|---------|-------------|
| `BMS_PORT` | `/dev/ttyUSB0` | Serial port of BMS adapter |
| `BMS_CELL_COUNT` | `24` | Number of cells (display only) |
| `POLL_INTERVAL` | `2` | Seconds between BMS polls |
| `WEB_HOST` | `0.0.0.0` | Bind address |
| `WEB_PORT` | `5000` | HTTP port |
| `SECRET_KEY` | `change_me` | Flask session secret (change this!) |
| `WEB_USERNAME` | `admin` | Login username |
| `WEB_PASSWORD` | `admin` | Login password (change this!) |
| `DATA_RETENTION_DAYS` | `90` | Days to keep log records |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `LOG_FILE` | `logs/bms_monitor.log` | Log file path |
| `CELL_VOLTAGE_MIN_WARN` | `3.0` | Cell undervoltage alert (V) |
| `CELL_VOLTAGE_MAX_WARN` | `3.65` | Cell overvoltage alert (V) |
| `TEMP_MAX_WARN` | `45` | Over-temperature alert (°C) |
| `SOC_MIN_WARN` | `10` | Low SOC alert (%) |

---

## Dependencies

- `flask` — Web framework
- `flask-socketio` + `eventlet` — WebSocket support
- `flask-login` — Session auth
- `python-dotenv` — `.env` loading
- `daly-bms` — Daly BMS UART protocol library
- `SQLAlchemy` — ORM / SQLite
- `pyserial` — Serial port access
