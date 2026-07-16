"""Command payloads dispatched by the Presentation layer to the
Application Controller (Module Specifications 2.7, 2.12).

Each command is immutable data; the handler that executes it belongs to
``application.services`` and is added when the corresponding module is
implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class StartCapture:
    """Requests that a new recording session begin (RF-001, RF-005)."""

    instance_url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StopCapture:
    """Requests that the active recording session be finalized (RF-007)."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class PauseCapture:
    """Requests that event persistence be suspended (RF-006)."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ResumeCapture:
    """Requests that a paused session resume persisting events (RF-006)."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureManualScreenshot:
    """Requests an on-demand screenshot during an active session (RF-024)."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RelabelArtifact:
    """Renames a page or element without altering the original evidence
    (RF-036)."""

    session_id: UUID
    artifact_id: UUID
    new_label: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExcludeEvent:
    """Removes a sensitive event from the export before finalization
    (RF-037)."""

    session_id: UUID
    event_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RecoverInterruptedSession:
    """Requests recovery of a session left in the ``interrupted`` state
    (RF-034)."""

    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenConfiguration:
    """Requests that the configuration screen be shown (RF-038)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExitApplication:
    """Requests a controlled application shutdown."""
