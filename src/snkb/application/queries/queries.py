"""Query payloads dispatched by the Presentation layer (read-only)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class GetSessionStatus:
    """Requests the current lifecycle status of a session."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class GetSessionStatistics:
    """Requests live counters (pages, elements, screenshots, errors)."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class GetRecentSessions:
    """Requests the list of sessions available for reopening in query mode
    (RF-035)."""

    limit: int = 20


@dataclass(frozen=True, slots=True, kw_only=True)
class GetNavigationTimeline:
    """Requests the ordered navigation timeline of a session for the
    Consulta screen (Module Specifications 2.9)."""

    session_id: UUID
