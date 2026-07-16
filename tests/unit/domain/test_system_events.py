"""Testes do evento transversal ``ErrorOccurred``."""

from __future__ import annotations

from uuid import UUID

from snkb.domain.enums.log_level import LogLevel
from snkb.domain.events.system_events import ErrorOccurred


def test_error_occurred_defaults_severity_to_error(fixed_session_uuid: UUID) -> None:
    event = ErrorOccurred(session_id=fixed_session_uuid, module="browser_manager", message="falha")

    assert event.severity == LogLevel.ERROR


def test_error_occurred_allows_no_session() -> None:
    event = ErrorOccurred(session_id=None, module="bootstrap", message="playwright ausente")

    assert event.session_id is None
