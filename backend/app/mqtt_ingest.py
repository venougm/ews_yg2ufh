"""paho-mqtt client, native EWS JSON parsing, store + broadcast.

NO aprslib: EWS nodes publish a single JSON object per reading (see
technical-design.md §4), so parsing is `json.loads` with validation, not APRS
packet decoding.

A single `paho.mqtt.client.Client` instance runs in a background thread started
from FastAPI's `lifespan` context. Immediately after constructing the `Client`,
`client.suppress_exceptions = True` is set -- defense-in-depth, because
paho-mqtt 1.6.1 defaults this flag to False and would otherwise re-raise an
exception escaping `on_message`, killing the client's background network thread
with no auto-restart. With the flag True, paho logs and swallows such an
exception instead, so an unanticipated gap degrades to "one reading dropped and
logged" rather than "ingestion is dead until a manual restart."

`on_message_impl` is structured as two separate try/except blocks with distinct
logging, so a storage/broadcast failure is never misreported as a parse failure.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

import paho.mqtt.client as mqtt

from app import db, ws_manager

logger = logging.getLogger(__name__)


class _Counter:
    """Simple counter so tests/metrics can observe parse-failure counts without
    a real metrics backend."""

    def __init__(self) -> None:
        self.count = 0

    def increment(self) -> None:
        self.count += 1


parse_failures_counter = _Counter()


def parse_payload(raw: bytes | str) -> dict[str, Any] | None:
    """Decode one EWS node JSON payload. Accepts `bytes` (matching the real
    `on_message` call site) or `str` (for unit tests). Never raises: returns
    `None` and logs on any JSON error or non-object payload, so "never crash the
    loop" is testable without a live MQTT client."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        parsed = json.loads(raw)
    except Exception as e:
        payload_repr = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        logger.warning("parse failure: payload=%r error=%s", payload_repr, e)
        parse_failures_counter.increment()
        return None

    if not isinstance(parsed, dict):
        logger.warning("parse failure: payload is not a JSON object: %r", parsed)
        parse_failures_counter.increment()
        return None
    return parsed


def evaluate_alarm(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Compare a reading's tilt against the node's resolved thresholds.

    Reads `payload['tilt']['delta']` (the primary tilt-change signal per the
    technical design), falling back to `['tilt']['x']`. Returns the higher of
    the two levels: AWAS when the value is >= tilt_awas, else SIAGA when
    >= tilt_siaga, else None. Never raises."""
    tilt = payload.get("tilt")
    if not isinstance(tilt, dict):
        return None

    value = tilt.get("delta")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        value = tilt.get("x")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    node_id = payload.get("id")
    if not node_id:
        return None

    thr = db.resolve_threshold(node_id)
    if value >= thr["tilt_awas"]:
        return {"level": "awas", "reason": f"tilt {value} deg >= awas {thr['tilt_awas']} deg"}
    if value >= thr["tilt_siaga"]:
        return {"level": "siaga", "reason": f"tilt {value} deg >= siaga {thr['tilt_siaga']} deg"}
    return None


def process_reading(
    payload: dict[str, Any],
    broadcast_fn: Callable[[dict[str, Any]], None],
    received_at: str | None = None,
) -> None:
    """Validate, store, and broadcast one EWS reading.

    Requires `payload['id']` to be a non-empty string; a payload without it is
    dropped (logged) with no store and no broadcast. On success stores the row,
    then broadcasts a single `{type:'reading', ...}` message; if the tilt
    evaluation yields an alarm, additionally broadcasts a `{type:'alarm', ...}`
    message.

    `received_at` is left None for live ingestion so `db.store_reading` stamps
    the current time; the broker-free injector may pass an explicit value."""
    node_id = payload.get("id")
    if not isinstance(node_id, str) or not node_id.strip():
        logger.warning("dropping reading with missing/empty 'id': payload=%r", payload)
        return

    alarm = evaluate_alarm(payload)
    received_at = db.store_reading(payload, received_at=received_at)

    reading_msg = {
        "type": "reading",
        "node_id": node_id,
        "kabupaten": payload.get("kabupaten"),
        "ts": payload.get("ts"),
        "received_at": received_at,
        "payload": payload,
        "alarm": alarm,
    }
    broadcast_fn(reading_msg)

    if alarm is not None:
        alarm_msg = {
            "type": "alarm",
            "level": alarm["level"],
            "source": node_id,
            "reason": alarm["reason"],
            "ts": payload.get("ts"),
        }
        broadcast_fn(alarm_msg)


def on_message_impl(
    topic: str,
    payload_bytes: bytes,
    broadcast_fn: Callable[[dict[str, Any]], None],
) -> None:
    """The actual logic behind paho's `on_message` callback, factored out so it
    is directly unit-testable without a real `mqtt.MQTTMessage`. Two separate
    try/except blocks: parse vs pipeline."""
    try:
        parsed = parse_payload(payload_bytes)
    except Exception as e:  # defensive: parse_payload already swallows, but be safe
        logger.warning("parse failure: topic=%s error=%s", topic, e)
        parse_failures_counter.increment()
        return

    if parsed is None:
        return

    try:
        process_reading(parsed, broadcast_fn)
    except Exception as e:
        logger.error(
            "ingestion pipeline failure after successful parse: node_id=%s error=%s",
            parsed.get("id"),
            e,
            exc_info=True,
        )
        return


def build_client(settings, main_loop) -> mqtt.Client:
    """Constructs and configures the paho Client per the design: suppress_exceptions,
    on_connect subscribes to `<prefix>/#` at QoS 1, reconnect_delay_set, on_disconnect
    logs a WARNING. on_message bridges to the WS manager on the main loop."""
    client = mqtt.Client(client_id=settings.mqtt_client_id)
    client.suppress_exceptions = True

    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def on_connect(client, userdata, flags, rc):
        topic = f"{settings.mqtt_topic_prefix}/#"
        client.subscribe(topic, qos=1)
        logger.info("MQTT connected, subscribed to %s", topic)

    def on_disconnect(client, userdata, rc):
        logger.warning("MQTT disconnected: rc=%s", rc)

    def on_message(client, userdata, msg):
        def broadcast(payload):
            ws_manager.manager.broadcast_json_threadsafe(payload, main_loop)

        on_message_impl(msg.topic, msg.payload, broadcast)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=60)

    return client
