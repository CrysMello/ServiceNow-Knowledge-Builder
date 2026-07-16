"""Frame entity: represents a document or iframe within a page (RF-009)."""

from __future__ import annotations

from dataclasses import dataclass

from snkb.domain.value_objects.identifiers import FrameId, PageId


@dataclass(slots=True)
class Frame:
    """A node in the frame tree of a page. The root document frame has
    ``parent_frame_id`` set to ``None``."""

    frame_id: FrameId
    page_id: PageId
    origin: str
    selector: str | None
    parent_frame_id: FrameId | None = None
