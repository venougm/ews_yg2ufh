"""Settings loader (EWS backend).

Precedence (highest wins): real environment variables > `.env` (loaded via
python-dotenv's `load_dotenv()` with its default `override=False`, so already-set
real environment variables always win over `.env` file contents) > `config.yaml` >
built-in defaults.

`MQTT_BROKER_HOST` is the only hard-required key with no safe default -- a missing
value raises `RuntimeError` at startup. `MQTT_TOPIC_PREFIX` is conceptually
required too, but unlike the APRS backend EWS has one natural owner-scoped prefix
('yg2ufh/ews'), so that is its documented default: loading settings with only
`MQTT_BROKER_HOST` set yields the full EWS defaults. An explicitly blank
`MQTT_TOPIC_PREFIX` still raises, since an empty prefix would subscribe to the
whole broker. Every other declared key is type/range-checked; an invalid value logs a WARNING
naming the offending key and falls back to the documented default instead of
raising, so a malformed value is caught at startup with a clear cause rather than
failing deep inside a query later.

ANTI-CONFLICT with the APRS backend (yg2ufh.mooo.com:8000): EWS defaults deliberately
differ so the two never collide on the shared broker -- client_id 'ews-web-backend'
(a shared client_id would kick APRS off the broker), topic prefix 'yg2ufh/ews',
HTTP port 8001, DB './data/ews.db'.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

_DEFAULTS: dict[str, Any] = {
    "MQTT_BROKER_PORT": 1883,
    "MQTT_CLIENT_ID": "ews-web-backend",
    "MQTT_TOPIC_PREFIX": "yg2ufh/ews",
    "HISTORY_LOOKBACK_HOURS": 24,
    "DB_PATH": "./data/ews.db",
    "LOG_LEVEL": "INFO",
    "HTTP_HOST": "0.0.0.0",
    "HTTP_PORT": 8001,
    "MISS_THRESHOLD_SEC": 180,
    "RETENTION_DAYS": 365,
}


@dataclass
class Settings:
    mqtt_broker_host: str
    mqtt_topic_prefix: str
    mqtt_broker_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "ews-web-backend"
    history_lookback_hours: int = 24
    db_path: str = "./data/ews.db"
    log_level: str = "INFO"
    http_host: str = "0.0.0.0"
    http_port: int = 8001
    miss_threshold_sec: int = 180
    retention_days: int = 365


def _load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _validate_int_range(key: str, raw: Any, default: int, lo: int, hi: int) -> int:
    try:
        value = int(raw)
        if not (lo <= value <= hi):
            raise ValueError(f"{value} out of range [{lo}, {hi}]")
        return value
    except (TypeError, ValueError) as exc:
        logger.warning(
            "config: invalid value for %s (%r): %s; falling back to default %r",
            key, raw, exc, default,
        )
        return default


def _validate_min_int(key: str, raw: Any, default: int, minimum: int) -> int:
    try:
        value = int(raw)
        if value < minimum:
            raise ValueError(f"{value} < {minimum}")
        return value
    except (TypeError, ValueError) as exc:
        logger.warning(
            "config: invalid value for %s (%r): %s; falling back to default %r",
            key, raw, exc, default,
        )
        return default


def _validate_log_level(raw: Any, default: str) -> str:
    value = str(raw).upper() if raw is not None else default
    if value not in _VALID_LOG_LEVELS:
        logger.warning(
            "config: invalid value for LOG_LEVEL (%r); falling back to default %r",
            raw, default,
        )
        return default
    return value


def load_settings(
    env_path: str | Path = ".env",
    config_path: str | Path = "config.yaml",
) -> Settings:
    # python-dotenv's load_dotenv default is override=False: real environment
    # variables already set always win over values from the .env file.
    load_dotenv(dotenv_path=env_path, override=False)

    yaml_values = _load_yaml(config_path)

    def get(key: str) -> Any:
        """env/.env (os.environ, since load_dotenv populated it) takes precedence
        over config.yaml, which takes precedence over the built-in default."""
        if key in os.environ:
            return os.environ[key]
        if key in yaml_values:
            return yaml_values[key]
        return _DEFAULTS.get(key)

    mqtt_broker_host = get("MQTT_BROKER_HOST")
    if not mqtt_broker_host:
        raise RuntimeError(
            "MQTT_BROKER_HOST is required (set it via environment variable or .env)"
        )

    mqtt_topic_prefix = get("MQTT_TOPIC_PREFIX")
    if not mqtt_topic_prefix:
        raise RuntimeError(
            "MQTT_TOPIC_PREFIX is required (set it via environment variable or config.yaml)"
        )

    mqtt_broker_port = _validate_int_range(
        "MQTT_BROKER_PORT", get("MQTT_BROKER_PORT"), _DEFAULTS["MQTT_BROKER_PORT"], 1, 65535
    )
    http_port = _validate_int_range(
        "HTTP_PORT", get("HTTP_PORT"), _DEFAULTS["HTTP_PORT"], 1, 65535
    )
    history_lookback_hours = _validate_min_int(
        "HISTORY_LOOKBACK_HOURS",
        get("HISTORY_LOOKBACK_HOURS"),
        _DEFAULTS["HISTORY_LOOKBACK_HOURS"],
        1,
    )
    miss_threshold_sec = _validate_min_int(
        "MISS_THRESHOLD_SEC",
        get("MISS_THRESHOLD_SEC"),
        _DEFAULTS["MISS_THRESHOLD_SEC"],
        1,
    )
    retention_days = _validate_min_int(
        "RETENTION_DAYS",
        get("RETENTION_DAYS"),
        _DEFAULTS["RETENTION_DAYS"],
        1,
    )
    log_level = _validate_log_level(get("LOG_LEVEL"), _DEFAULTS["LOG_LEVEL"])

    mqtt_username = get("MQTT_USERNAME") or None
    mqtt_password = get("MQTT_PASSWORD") or None
    mqtt_client_id = get("MQTT_CLIENT_ID") or _DEFAULTS["MQTT_CLIENT_ID"]
    db_path = get("DB_PATH") or _DEFAULTS["DB_PATH"]
    http_host = get("HTTP_HOST") or _DEFAULTS["HTTP_HOST"]

    return Settings(
        mqtt_broker_host=str(mqtt_broker_host),
        mqtt_topic_prefix=str(mqtt_topic_prefix),
        mqtt_broker_port=mqtt_broker_port,
        mqtt_username=mqtt_username,
        mqtt_password=mqtt_password,
        mqtt_client_id=str(mqtt_client_id),
        history_lookback_hours=history_lookback_hours,
        db_path=str(db_path),
        log_level=log_level,
        http_host=str(http_host),
        http_port=http_port,
        miss_threshold_sec=miss_threshold_sec,
        retention_days=retention_days,
    )


_settings_cache: Settings | None = None


def get_settings() -> Settings:
    """Cached singleton accessor, so modules that need `Settings` at import
    time (e.g. a router's `Query(default=get_settings().history_lookback_hours)`)
    all see the same loaded configuration without re-reading `.env`/`config.yaml`
    on every call."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = load_settings()
    return _settings_cache


def reset_settings_cache() -> None:
    """Test helper: forces the next get_settings() call to reload."""
    global _settings_cache
    _settings_cache = None
