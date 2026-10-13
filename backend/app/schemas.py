"""Pydantic response/request models for the EWS REST API.

`payload: dict | None` and `alarm: dict | None` are typed to always be present in
the serialized output (never omitted) -- matching the WebSocket broadcast
contract's rule: the key is always present, value is `null` when absent.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


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


class NodeIn(BaseModel):
    """Request body for registering a node (POST /api/nodes). Only editable
    fields -- the read-only NodeOut computed fields (status/ts/received_at/
    payload/alarm) are never accepted from clients. node_id is the MQTT-matching
    identity: it is trimmed and must be non-empty."""

    node_id: str
    nama: str | None = None
    tipe: str | None = None
    kabupaten: str | None = None
    kecamatan: str | None = None
    lat: float | None = None
    lon: float | None = None
    lokasi: str | None = None

    @field_validator("node_id")
    @classmethod
    def _node_id_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("node_id wajib diisi")
        return v

    @field_validator("lat")
    @classmethod
    def _lat_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (-90.0 <= v <= 90.0):
            raise ValueError("lat harus di antara -90 dan 90")
        return v

    @field_validator("lon")
    @classmethod
    def _lon_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (-180.0 <= v <= 180.0):
            raise ValueError("lon harus di antara -180 dan 180")
        return v


class NodeUpdateIn(BaseModel):
    """Request body for editing a node (PUT /api/nodes/{node_id}). Identical to
    NodeIn minus node_id: the path supplies the (locked) node_id, which must
    never change on edit because it is the identity used to match MQTT data."""

    nama: str | None = None
    tipe: str | None = None
    kabupaten: str | None = None
    kecamatan: str | None = None
    lat: float | None = None
    lon: float | None = None
    lokasi: str | None = None

    @field_validator("lat")
    @classmethod
    def _lat_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (-90.0 <= v <= 90.0):
            raise ValueError("lat harus di antara -90 dan 90")
        return v

    @field_validator("lon")
    @classmethod
    def _lon_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (-180.0 <= v <= 180.0):
            raise ValueError("lon harus di antara -180 dan 180")
        return v


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
