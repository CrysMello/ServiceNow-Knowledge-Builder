"""Screenshot entity: evidence metadata for a captured image
(SRS section 10, Module Specifications Chapter 8, section 8.12)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from snkb.domain.enums.screenshot_type import ScreenshotType
from snkb.domain.value_objects.identifiers import PageId, ScreenshotId, SessionId


@dataclass(slots=True)
class Screenshot:
    """Metadata describing one captured PNG evidence file. The binary
    content itself is written to disk exclusively by the Export Engine."""

    screenshot_id: ScreenshotId
    session_id: SessionId
    page_id: PageId
    captured_at: datetime
    capture_type: ScreenshotType
    file_name: str
    width: int
    height: int
