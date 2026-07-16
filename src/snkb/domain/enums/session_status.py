"""Session lifecycle states (SRS section 9.4)."""

from __future__ import annotations

from enum import StrEnum


class SessionStatus(StrEnum):
    """Allowed states for a recording session. Invalid transitions must be
    rejected and logged by the module that owns the state machine."""

    CREATED = "created"
    PREPARING = "preparing"
    WAITING_AUTHENTICATION = "waiting_authentication"
    READY = "ready"
    RECORDING = "recording"
    PAUSED = "paused"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    RECOVERED = "recovered"
