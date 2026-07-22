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


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidateExport:
    """Requests integrity validation of a session already exported to
    disk (RF-039, ADR 0014)."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class GetSessionLogs:
    """Requests the persisted log records of a session, most recent
    first (ADR 0014)."""

    session_id: UUID
    limit: int = 200


@dataclass(frozen=True, slots=True, kw_only=True)
class GetEffectiveConfiguration:
    """Requests the application configuration currently in effect
    (Configuration Manager, ADR 0015)."""
