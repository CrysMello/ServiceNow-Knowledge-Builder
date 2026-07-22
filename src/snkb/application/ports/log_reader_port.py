"""Port for reading log records already persisted to disk by a previous
``snkb record`` process (``snkb logs``).

Distinct from ``LogEnginePort``: that port only exposes the in-memory
record of the *current* process (``export()``/``statistics()``). Reading
a previous session's logs requires parsing the JSON Lines files the Log
Engine already writes to ``logs/`` (ADR 0011, ADR 0014).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class LogRecordSummary:
    """One log entry belonging to a specific session, read from disk."""

    timestamp: datetime
    level: str
    module: str
    message: str


class LogReaderPort(Protocol):
    """Reads persisted log records for a given session, most recent
    first."""

    def read_session_logs(self, session_id: UUID, limit: int = 200) -> list[LogRecordSummary]: ...
