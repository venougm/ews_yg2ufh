"""FastAPI app assembly: lifespan, background tasks, router includes, static mount.

On startup: load settings, set the log level, init the DB, capture
`main_loop = asyncio.get_running_loop()`, build + connect the paho client (connect
wrapped in try/except -> WARNING so a dead broker never crashes the process),
`client.loop_start()`, then start two asyncio background tasks:

  - offline detection (~every 30s): flip newly-stale nodes to 'offline' and
    broadcast a `{type:'alarm', level:'siaga', ...}` notification (per
    technical-design.md §6 a silent node is itself an alarm).
  - retention (~every 6h): purge readings older than `retention_days`.

On shutdown: cancel both tasks, `client.loop_stop()`, `client.disconnect()`.

Routers are included under /api and /ws first, then the GET /node.html page
route; StaticFiles is mounted at "/" LAST so all of those take precedence.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import auth_seed, db, mqtt_ingest, ws_manager
from app.config import get_settings
from app.routers import auth, nodes, regions, thresholds, users, ws

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_OFFLINE_CHECK_INTERVAL_SEC = 30
_RETENTION_INTERVAL_SEC = 6 * 3600

_STATIC_DIR = Path(__file__).parent / "static"
_NODE_PAGE = _STATIC_DIR / "node.html"


async def _offline_detection_loop(settings) -> None:
    """Flip newly-stale nodes to 'offline' and broadcast a siaga alarm. A node
    that goes silent may just be low on battery -- or may have been buried by a
    landslide -- so silence is treated as an alarm (technical-design.md §6)."""
    while True:
        try:
            await asyncio.sleep(_OFFLINE_CHECK_INTERVAL_SEC)
            now = datetime.now(timezone.utc)
            stale = await asyncio.to_thread(db.get_stale_nodes, settings.miss_threshold_sec, now)
            for node_id in stale:
                await asyncio.to_thread(db.set_status, node_id, "offline")
                await ws_manager.manager.broadcast_json(
                    {
                        "type": "alarm",
                        "level": "siaga",
                        "source": node_id,
                        "reason": "node silent",
                        "ts": int(now.timestamp()),
                    }
                )
                logger.warning("node %s flagged offline (silent)", node_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("offline-detection loop error: %s", e, exc_info=True)


async def _retention_loop(settings) -> None:
    while True:
        try:
            await asyncio.sleep(_RETENTION_INTERVAL_SEC)
            now = datetime.now(timezone.utc)
            deleted = await asyncio.to_thread(db.purge_old_readings, settings.retention_days, now)
            if deleted:
                logger.info("retention purge removed %d old readings", deleted)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("retention loop error: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)

    db.init_db(settings.db_path)
    auth_seed.seed_users(settings)

    main_loop = asyncio.get_running_loop()
    client = mqtt_ingest.build_client(settings, main_loop)

    try:
        client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    except Exception as e:
        # A broker unreachable at startup must not crash the process -- paho's
        # own reconnect logic (loop_start + reconnect_delay_set) keeps retrying.
        logger.warning("initial MQTT connect failed, will keep retrying: %s", e)

    client.loop_start()
    app.state.mqtt_client = client

    offline_task = asyncio.create_task(_offline_detection_loop(settings))
    retention_task = asyncio.create_task(_retention_loop(settings))

    yield

    for task in (offline_task, retention_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    client.loop_stop()
    client.disconnect()


app = FastAPI(lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    SessionMiddleware,
    secret_key=_settings.session_secret,
    same_site="lax",
    https_only=_settings.cookie_secure,
    session_cookie="ews_session",
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(nodes.router, prefix="/api")
app.include_router(regions.router, prefix="/api")
app.include_router(thresholds.router, prefix="/api")
app.include_router(ws.router, prefix="/ws")


@app.get("/node.html", include_in_schema=False)
def node_page():
    """Per-node detail page (Chart.js tilt/weather/power charts). The page is
    static; its JS reads the node_id from the URL query string."""
    return FileResponse(_NODE_PAGE, media_type="text/html")


app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
