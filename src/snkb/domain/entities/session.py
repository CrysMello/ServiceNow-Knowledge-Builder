"""Session entity: administrative context of a recording (SRS section 10.2,
Module Specifications Chapter 4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.value_objects.identifiers import SessionId
from snkb.domain.value_objects.viewport import Resolution, Viewport


@dataclass(slots=True)
class Session:
    """Administrative context shared by every artifact produced during a
    recording. The Session Manager is the only module authorized to hold
    a mutable reference to this entity (see Module Specifications, 4.16)."""

    session_id: SessionId
    instance_url: str
    created_at: datetime
    status: SessionStatus

    recording_start: datetime | None = None
    recording_end: datetime | None = None
    instance_name: str | None = None
    home_title: str | None = None

    service_now_version: str | None = None
    service_now_version_source: str | None = None

    language: str | None = None
    locale: str | None = None
    timezone: str | None = None

    browser: str | None = None
    browser_version: str | None = None
    operating_system: str | None = None
    screen_resolution: Resolution | None = None
    viewport: Viewport | None = None
    device_scale_factor: float | None = None
    zoom: float | None = None
    theme: str | None = None

    authenticated_user: str | None = None

    warnings: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        """Active recording duration, or ``None`` while still running."""
        if self.recording_start is None or self.recording_end is None:
            return None
        return (self.recording_end - self.recording_start).total_seconds()
