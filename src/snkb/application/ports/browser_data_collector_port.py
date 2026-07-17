"""Port for the Browser Data Collector — the bridge between the real
browser (Playwright, infrastructure-only) and Element Recorder,
Selector Analyzer and Screenshot Engine (ADR 0013).

Never references Playwright types (``Page``, ``Browser``,
``BrowserContext``): only the infrastructure implementation
(``infrastructure.browser.browser_data_collector``) is authorized to
hold those (ARQ-001, PW-001, PW-006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class PageCaptureResult:
    """Summary of one successful capture cycle — never duplicates the
    full data already returned by the domain entities (``Page``,
    ``Element``) that Navigation Recorder/Element Recorder already
    expose; callers that need the full data query those modules
    directly by ``page_id``/``element_id``."""

    session_id: UUID
    page_id: UUID
    url: str
    title: str
    element_count: int
    new_element_count: int
    screenshot_id: UUID | None
    captured_at: datetime
    warnings: tuple[str, ...] = field(default_factory=tuple)


class BrowserDataCollectorPort(Protocol):
    """Observes the real browser for one recording session and feeds
    Element Recorder, Selector Analyzer and Screenshot Engine with real
    data, associated to the page the Navigation Recorder already
    tracks."""

    async def start(self, session_id: UUID) -> None: ...
    async def capture_current_page(self) -> PageCaptureResult | None: ...
    async def stop(self) -> None: ...
