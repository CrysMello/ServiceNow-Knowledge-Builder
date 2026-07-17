"""Testes do ``SessionManager`` — puros, sem I/O (Module Specifications,
Capítulo 4)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest

from snkb.domain.entities.session import Session
from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.events.session_events import (
    SessionCreated,
    SessionExpired,
    SessionFailed,
    SessionFinished,
    SessionPaused,
    SessionResumed,
    SessionStarted,
    SessionTimeout,
)
from snkb.domain.exceptions.session_exceptions import (
    InvalidMetadataError,
    InvalidSessionTransitionError,
    SessionAlreadyExistsError,
    SessionNotActiveError,
)
from snkb.domain.value_objects.viewport import Resolution
from snkb.modules.session.session_manager import SessionManager

_INSTANCE_URL = "https://empresa.service-now.com"


class _RecordingEventPublisher:
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)

    def of_type(self, event_type: type) -> list[object]:
        return [event for event in self.published if isinstance(event, event_type)]


class _RecordingLogEngine:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def trace(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def debug(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def info(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def warning(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def error(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def critical(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def exception(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def flush(self) -> None:
        """Nenhuma escrita real ocorre neste duplo de teste."""

    def export(self) -> list[dict[str, object]]:
        return []

    def statistics(self) -> dict[str, object]:
        return {}


def _sequential_uuid_factory() -> Callable[[], UUID]:
    counter = itertools.count(1)
    return lambda: UUID(int=next(counter))


def _make_manager(
    generate_session_id: Callable[[], UUID] | None = None,
    now: Callable[[], datetime] | None = None,
) -> tuple[SessionManager, _RecordingEventPublisher, _RecordingLogEngine]:
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()
    manager = SessionManager(
        event_publisher=publisher,
        log_engine=log,
        now=now or (lambda: datetime(2026, 7, 16, 9, 0, 0, tzinfo=UTC)),
        generate_session_id=generate_session_id or _sequential_uuid_factory(),
    )
    return manager, publisher, log


def _advance_to_recording(manager: SessionManager, session_id: UUID) -> None:
    manager.mark_preparing(session_id)
    manager.mark_waiting_authentication(session_id)
    manager.mark_ready(session_id)
    manager.start_session(session_id)


# ----------------------------------------------------------------------
# create_session
# ----------------------------------------------------------------------


def test_create_session_returns_a_session_with_created_status() -> None:
    manager, publisher, _log = _make_manager()

    session = manager.create_session(_INSTANCE_URL)

    assert isinstance(session, Session)
    assert session.status == SessionStatus.CREATED
    assert session.instance_url == _INSTANCE_URL
    created_events = publisher.of_type(SessionCreated)
    assert len(created_events) == 1
    assert created_events[0].session_id == session.session_id.value


def test_create_session_rejects_a_colliding_session_id() -> None:
    fixed_id = UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")
    manager, _publisher, _log = _make_manager(generate_session_id=lambda: fixed_id)
    manager.create_session(_INSTANCE_URL)

    with pytest.raises(SessionAlreadyExistsError):
        manager.create_session(_INSTANCE_URL)


# ----------------------------------------------------------------------
# Fluxo de vida completo
# ----------------------------------------------------------------------


def test_full_lifecycle_reaches_completed_without_warnings() -> None:
    manager, publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value

    _advance_to_recording(manager, session_id)
    assert manager.get_session(session_id).status == SessionStatus.RECORDING
    assert manager.get_session(session_id).recording_start is not None

    manager.pause_session(session_id)
    assert manager.get_session(session_id).status == SessionStatus.PAUSED

    manager.resume_session(session_id)
    assert manager.get_session(session_id).status == SessionStatus.RECORDING

    manager.finish_session(session_id)
    finished = manager.get_session(session_id)
    assert finished.status == SessionStatus.COMPLETED
    assert finished.recording_end is not None

    assert [type(event) for event in publisher.published] == [
        SessionCreated,
        SessionStarted,
        SessionPaused,
        SessionResumed,
        SessionFinished,
    ]


def test_finish_session_with_warnings_completes_with_warnings_status() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value
    _advance_to_recording(manager, session_id)
    manager.get_session(session_id).warnings.append("Elemento sensível mascarado.")

    manager.finish_session(session_id)

    assert manager.get_session(session_id).status == SessionStatus.COMPLETED_WITH_WARNINGS


def test_is_active_reflects_terminal_vs_non_terminal_status() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value

    assert manager.is_active(session_id) is True

    _advance_to_recording(manager, session_id)
    manager.finish_session(session_id)

    assert manager.is_active(session_id) is False


# ----------------------------------------------------------------------
# Cancelamento, expiração e timeout
# ----------------------------------------------------------------------


def test_cancel_session_from_recording_publishes_session_failed() -> None:
    manager, publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value
    _advance_to_recording(manager, session_id)

    manager.cancel_session(session_id)

    assert manager.get_session(session_id).status == SessionStatus.INTERRUPTED
    failed_events = publisher.of_type(SessionFailed)
    assert len(failed_events) == 1
    assert failed_events[0].reason == "Sessão cancelada pelo usuário."


def test_cancel_session_from_created_is_allowed() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)

    manager.cancel_session(session.session_id.value)

    assert manager.get_session(session.session_id.value).status == SessionStatus.INTERRUPTED


def test_expire_session_moves_to_failed_and_publishes_session_expired() -> None:
    manager, publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value
    _advance_to_recording(manager, session_id)

    manager.expire_session(session_id)

    assert manager.get_session(session_id).status == SessionStatus.FAILED
    expired_events = publisher.of_type(SessionExpired)
    assert len(expired_events) == 1
    assert expired_events[0].session_id == session_id


def test_timeout_session_only_allowed_before_recording_starts() -> None:
    manager, publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value
    manager.mark_preparing(session_id)
    manager.mark_waiting_authentication(session_id)

    manager.timeout_session(session_id)

    assert manager.get_session(session_id).status == SessionStatus.FAILED
    timeout_events = publisher.of_type(SessionTimeout)
    assert len(timeout_events) == 1
    assert timeout_events[0].session_id == session_id


def test_timeout_session_rejected_once_recording() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value
    _advance_to_recording(manager, session_id)

    with pytest.raises(InvalidSessionTransitionError):
        manager.timeout_session(session_id)


def test_recover_session_allows_recording_to_restart() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value
    _advance_to_recording(manager, session_id)
    manager.cancel_session(session_id)

    manager.recover_session(session_id)
    assert manager.get_session(session_id).status == SessionStatus.RECOVERED

    manager.start_session(session_id)
    assert manager.get_session(session_id).status == SessionStatus.RECORDING


# ----------------------------------------------------------------------
# Transições inválidas
# ----------------------------------------------------------------------


def test_start_session_directly_from_created_is_rejected() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)

    with pytest.raises(InvalidSessionTransitionError):
        manager.start_session(session.session_id.value)


def test_pause_session_when_not_recording_is_rejected() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)

    with pytest.raises(InvalidSessionTransitionError):
        manager.pause_session(session.session_id.value)


def test_operations_on_unknown_session_raise_session_not_active_error() -> None:
    manager, _publisher, _log = _make_manager()
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    with pytest.raises(SessionNotActiveError):
        manager.get_session(unknown_id)
    with pytest.raises(SessionNotActiveError):
        manager.start_session(unknown_id)
    with pytest.raises(SessionNotActiveError):
        manager.get_statistics(unknown_id)


# ----------------------------------------------------------------------
# Estatísticas e metadados
# ----------------------------------------------------------------------


def test_get_statistics_reports_status_and_duration() -> None:
    ticks = iter(
        [
            datetime(2026, 7, 16, 8, 55, 0, tzinfo=UTC),  # created_at
            datetime(2026, 7, 16, 9, 0, 0, tzinfo=UTC),  # recording_start
            datetime(2026, 7, 16, 9, 30, 0, tzinfo=UTC),  # recording_end
        ]
    )
    manager, _publisher, _log = _make_manager(now=lambda: next(ticks))
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value
    _advance_to_recording(manager, session_id)

    manager.finish_session(session_id)
    stats = manager.get_statistics(session_id)

    assert stats["status"] == "completed"
    assert stats["duration_seconds"] == pytest.approx(1800.0)
    assert stats["warnings_count"] == 0


def test_update_metadata_sets_known_fields() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)
    session_id = session.session_id.value

    manager.update_metadata(
        session_id,
        {
            "browser": "Chromium",
            "browser_version": "126.0",
            "operating_system": "Windows 11",
            "screen_resolution": Resolution(width=1920, height=1080),
        },
    )

    updated = manager.get_session(session_id)
    assert updated.browser == "Chromium"
    assert updated.screen_resolution == Resolution(width=1920, height=1080)


def test_update_metadata_rejects_unknown_fields() -> None:
    manager, _publisher, _log = _make_manager()
    session = manager.create_session(_INSTANCE_URL)

    with pytest.raises(InvalidMetadataError):
        manager.update_metadata(session.session_id.value, {"session_id": "nope"})
