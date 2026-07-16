"""Schema for ``session.json`` (SRS section 10.2, RF-027)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScreenResolutionModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    width: int
    height: int


class ViewportModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    width: int
    height: int


class SessionJsonModel(BaseModel):
    """Serializable representation of ``session.json``.

    Fields marked optional in SRS 10.2 default to ``None`` and must be
    rendered as JSON ``null``, never omitted (RF-027).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str
    recording_id: UUID
    instance_url: str
    instance_name: str | None = None
    home_title: str | None = None

    recording_start: datetime
    recording_end: datetime | None = None
    duration_seconds: float | None = None

    status: str

    service_now_version: str | None = None
    service_now_version_source: str | None = None

    language: str | None = None
    locale: str | None = None
    timezone: str | None = None

    browser: str
    browser_version: str
    operating_system: str
    screen_resolution: ScreenResolutionModel
    viewport: ViewportModel
    device_scale_factor: float | None = None
    zoom: float | None = None
    theme: str | None = None

    authenticated_user: str | None = None

    configuration_snapshot: dict[str, object] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
