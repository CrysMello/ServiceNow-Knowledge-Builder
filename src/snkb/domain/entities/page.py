"""Page entity: a logical screen visited during the session
(SRS section 10.4, Module Specifications Chapter 5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from snkb.domain.value_objects.identifiers import ElementId, PageId, ScreenshotId, SessionId
from snkb.domain.value_objects.url import NormalizedUrl


@dataclass(slots=True)
class Page:
    """A distinct screen identified by URL, title or DOM fingerprint change
    (RF-008, RN-006, RN-008)."""

    page_id: PageId
    session_id: SessionId
    name_original: str
    title: str
    url: NormalizedUrl
    fingerprint: str
    first_seen: datetime

    revision_id: int = 1
    name_reviewed: str | None = None
    route: str | None = None
    last_seen: datetime | None = None
    parent_context: str | None = None

    element_ids: list[ElementId] = field(default_factory=list)
    screenshot_ids: list[ScreenshotId] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
