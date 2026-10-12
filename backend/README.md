# EWS_YG2UFH Backend

FastAPI backend for the IoT landslide Early Warning System (EWS). Ingests EWS
node JSON from MQTT (`yg2ufh/ews/#`, parsed natively — no aprslib), stores it to
SQLite with the full region hierarchy (kabupaten / kecamatan / nodes /
readings / thresholds), serves a REST API + WebSocket, detects offline nodes in
the backend, and enforces 12-month (365-day) retention.

---

## ⚠️ ANTI-CONFLICT (READ BEFORE RUNNING)

This backend shares the MQTT broker with the **live APRS backend** that runs on
`yg2ufh.mooo.com:8000`. That APRS service is in production and must not be
disturbed. To avoid any collision, the EWS backend MUST use its own resources:

| Resource        | EWS value           | Why it matters                                             |
| --------------- | ------------------- | ---------------------------------------------------------- |
| HTTP port       | **8001**            | APRS already owns `:8000`.                                 |
| MQTT client_id  | **`ews-web-backend`** | A shared client_id kicks APRS off the broker (MOST CRITICAL). |
| MQTT topic      | **`yg2ufh/ews`** (subscribe `yg2ufh/ews/#`) | Keeps EWS traffic off the APRS topics.     |
| SQLite DB       | **`ews.db`** (`./data/ews.db`) | Separate datastore from APRS.                     |

**NEVER connect to the production broker `yg2ufh.mooo.com` in automated tests.**
The APRS service on `:8000` is live, and the EWS tests must stay broker-free. No
local mosquitto is required: the test suite and `tools/inject_sample.py` drive
the ingest pipeline directly, with no network broker involved. The node
simulator uses yet another client_id (`ews-node-sim`) so it never clashes with
the backend either.

---

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` (or `config.yaml.example` to `config.yaml`) and
set `MQTT_BROKER_HOST` + `MQTT_TOPIC_PREFIX` (both required). The anti-conflict
defaults above (port 8001, client_id `ews-web-backend`, topic `yg2ufh/ews`, db
`./data/ews.db`) are already baked into the config and the example files.

## Run

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Then open `http://127.0.0.1:8001/` for the dashboard. A dead/unreachable broker
never crashes the app — startup logs a warning and the HTTP API keeps serving.

## Local testing WITHOUT external hardware or a broker

No physical nodes and no mosquitto are needed to exercise the system locally.
Pick either option:

- **Broker-free injection (simplest).** Feed sample readings straight through
  the ingest pipeline:

  ```powershell
  .venv\Scripts\python.exe tools\inject_sample.py
  ```

  This stores sample nodes and prints their node_ids, exercising storage +
  alarm evaluation with no broker.

- **Local mosquitto + simulator.** If you do have a local broker on
  `127.0.0.1:1883`, publish realistic node JSON with the simulator (its
  client_id defaults to `ews-node-sim`, never `ews-web-backend`):

  ```powershell
  .venv\Scripts\python.exe tools\simulate_node.py            # publish every 5s
  .venv\Scripts\python.exe tools\simulate_node.py --once     # one round, then exit
  ```

## Run the tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

No test connects to a live broker (see ANTI-CONFLICT above).

## REST API (technical-design.md §12.6)

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

The WebSocket endpoint is `/ws/live` (the §12.6 sketch wrote `/ws`). It is
push-only: the server emits `{type:'reading', ...}` on each stored reading and
`{type:'alarm', level, source, reason, ts}` when a tilt threshold is crossed or
a node goes silent.

## Scope — what is TAHAP 2 and intentionally NOT built here

The following are explicitly out of scope for TAHAP 1 and are **not implemented**
in this backend. They are deferred to TAHAP 2:

- **Real PDF export** — there is no `POST /api/report` endpoint; report
  generation (ReportLab/WeasyPrint) is TAHAP 2.
- **Real auth / login / chat** — no authentication, session, or chat backend.
  An RBAC role badge may appear in the UI, but there is no real backend
  enforcement behind it.
- **Alarm-sound editing** — editing/uploading the siren/alarm sound that gets
  sent to the device is TAHAP 2. The dashboard plays a built-in Web Audio beep
  only; there is no sound-file management here.

The physical siren is MANUAL-only: the backend evaluates alarms and PUBLISHES a
notification, but never auto-fires a siren.
