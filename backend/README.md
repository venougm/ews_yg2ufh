# EWS_YG2UFH Backend

FastAPI backend for the IoT landslide Early Warning System (EWS). Ingests EWS
node JSON from MQTT (`yg2ufh/ews/#`, parsed natively — no aprslib), stores it to
SQLite with the full region hierarchy, serves a REST API + WebSocket, detects
offline nodes, and enforces 12-month retention.

> ANTI-CONFLICT: this backend shares the broker with the live APRS backend on
> `yg2ufh.mooo.com:8000`. It MUST use different resources — HTTP port **8001**,
> MQTT client_id **`ews-web-backend`**, topic prefix **`yg2ufh/ews`**, DB
> **`./data/ews.db`**. A shared MQTT client_id would kick APRS off the broker.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` (or `config.yaml.example` to `config.yaml`) and
set `MQTT_BROKER_HOST` + `MQTT_TOPIC_PREFIX` (both required).

## Run

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Test

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

## Tools

- `tools/simulate_node.py` — standalone MQTT publisher (client_id `ews-node-sim`,
  never the backend's). `--once` publishes a single round.
- `tools/inject_sample.py` — broker-free demo: feeds sample readings straight
  through the ingest pipeline (works with no mosquitto installed).

## REST API

```
GET  /api/kabupaten                      list kabupaten
POST /api/kabupaten                      add kabupaten
GET  /api/kabupaten/{kab}/kecamatan      list kecamatan in a kabupaten
POST /api/kabupaten/{kab}/kecamatan      add kecamatan
GET  /api/nodes?kabupaten=&kecamatan=    nodes + latest reading (filtered)
POST /api/nodes                          manually register a node
GET  /api/nodes/{id}                     node detail + latest (404 if unknown)
GET  /api/nodes/{id}/history?hours=N     reading history (grafik)
GET  /api/thresholds                     global + per-node overrides
PUT  /api/thresholds                     set global or node:<id> threshold
WS   /ws/live                            realtime push (reading + alarm)
GET  /node.html                          per-node detail page
GET  /                                   dashboard (static)
```

PDF export (`POST /api/report`) is TAHAP 2 and intentionally not implemented.
