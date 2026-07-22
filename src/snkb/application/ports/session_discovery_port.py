"""Port for session discovery on disk.

Every ``snkb <comando>`` invocation is a new process; ``SessionManager``
and the other central modules only keep state in memory, which does not
survive the process that recorded the session. ``status``/``validate``/
``open``/``logs`` need to find "the most recent session" by reading the
artifacts already exported to ``output_directory/<session_id>/``
(``session.json``, ``statistics.json``) — a responsibility distinct from
the Application Controller itself (ADR 0012, "Consequências"; ADR 0014).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionSummary:
    """Summary of one exported session, read from disk — never duplicates
    the full ``session.json``/``statistics.json`` content, only what the
    CLI's ``status``/``validate``/``open``/``logs`` commands need to
    identify and describe a session."""

    session_id: UUID
    status: str
    instance_url: str
    export_directory: Path
    recording_start: datetime
    recording_end: datetime | None
    total_pages: int
    total_elements: int
    total_screenshots: int
    error_count: int


class SessionDiscoveryPort(Protocol):
    """Finds sessions already exported to disk by a previous ``snkb
    record`` process."""

    def list_recent(self, limit: int = 20) -> list[SessionSummary]: ...
    def find(self, session_id: UUID) -> SessionSummary | None: ...
