"""Pydantic response/request models for the EWS REST API.

`payload: dict | None` and `alarm: dict | None` are typed to always be present in
the serialized output (never omitted) -- matching the WebSocket broadcast
contract's rule: the key is always present, value is `null` when absent.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class KabupatenOut(BaseModel):
    id: str
    nama: str
    provinsi: str | None = None


class KecamatanOut(BaseModel):
    id: str
    nama: str
    kabupaten_id: str


class NodeOut(BaseModel):
    node_id: str
    nama: str | None = None
    tipe: str | None = None
    kabupaten: str | None = None
    kecamatan: str | None = None
    lat: float | None = None
    lon: float | None = None
    status: str | None = None
    ts: int | None = None
    received_at: str | None = None
    payload: dict[str, Any] | None = None
    alarm: dict[str, Any] | None = None


class HistoryPointOut(BaseModel):
    received_at: str
    ts: int | None = None
    payload: dict[str, Any] | None = None


class ThresholdOut(BaseModel):
    scope: str
    tilt_siaga: float
    tilt_awas: float


class ThresholdIn(BaseModel):
    scope: str
    tilt_siaga: float
    tilt_awas: float


class LoginIn(BaseModel):
    username: str
    password: str


class UserCreateIn(BaseModel):
    username: str
    password: str
    role: str


class UserOut(BaseModel):
    username: str
    role: str
    created_at: str
