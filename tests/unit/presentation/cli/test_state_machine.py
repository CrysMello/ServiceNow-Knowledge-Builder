"""Testes da máquina de estados da CLI (livre de I/O de terminal)."""

from __future__ import annotations

from uuid import UUID

from snkb.domain.events.browser_events import BrowserCrashed, BrowserStarted, LoginDetected
from snkb.domain.events.export_events import ExportCompleted, ExportFailed, ExportStarted
from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.session_events import SessionStarted
from snkb.domain.events.system_events import ErrorOccurred
from snkb.presentation.cli.state import RecordingState
from snkb.presentation.cli.state_machine import RecordingStateMachine


def test_initial_state_is_idle() -> None:
    machine = RecordingStateMachine()

    assert machine.state == RecordingState.IDLE
    assert machine.can_start_capture() is True
    assert machine.can_stop_capture() is False


def test_browser_started_moves_to_waiting_login(fixed_session_uuid: UUID) -> None:
    machine = RecordingStateMachine()

    new_state = machine.apply(BrowserStarted(session_id=fixed_session_uuid))

    assert new_state == RecordingState.WAITING_LOGIN
    assert machine.can_stop_capture() is True
    assert machine.can_start_capture() is False


def test_login_detected_or_session_started_moves_to_recording(fixed_session_uuid: UUID) -> None:
    via_login = RecordingStateMachine()
    via_login.apply(LoginDetected(session_id=fixed_session_uuid))
    assert via_login.state == RecordingState.RECORDING

    via_session = RecordingStateMachine()
    via_session.apply(SessionStarted(session_id=fixed_session_uuid))
    assert via_session.state == RecordingState.RECORDING


def test_export_lifecycle_transitions(fixed_session_uuid: UUID) -> None:
    machine = RecordingStateMachine(state=RecordingState.RECORDING)

    machine.apply(ExportStarted(session_id=fixed_session_uuid))
    assert machine.state == RecordingState.EXPORTING

    machine.apply(ExportCompleted(session_id=fixed_session_uuid, output_directory="exports/x"))
    assert machine.state == RecordingState.FINISHED
    assert machine.can_start_capture() is True


def test_export_failed_moves_to_error(fixed_session_uuid: UUID) -> None:
    machine = RecordingStateMachine(state=RecordingState.EXPORTING)

    machine.apply(ExportFailed(session_id=fixed_session_uuid, reason="disco cheio"))

    assert machine.state == RecordingState.ERROR
    assert machine.can_start_capture() is True


def test_browser_crashed_moves_to_interrupted(fixed_session_uuid: UUID) -> None:
    machine = RecordingStateMachine(state=RecordingState.RECORDING)

    machine.apply(BrowserCrashed(session_id=fixed_session_uuid, reason="fechado pelo usuário"))

    assert machine.state == RecordingState.INTERRUPTED
    assert machine.can_start_capture() is True


def test_error_occurred_moves_to_error(fixed_session_uuid: UUID) -> None:
    machine = RecordingStateMachine(state=RecordingState.RECORDING)

    machine.apply(
        ErrorOccurred(session_id=fixed_session_uuid, module="browser_manager", message="falha")
    )

    assert machine.state == RecordingState.ERROR


def test_unrecognized_event_does_not_change_state(fixed_session_uuid: UUID) -> None:
    machine = RecordingStateMachine(state=RecordingState.RECORDING)

    machine.apply(
        PageCaptured(
            session_id=fixed_session_uuid,
            page_id=UUID("00000000-0000-0000-0000-000000000099"),
            normalized_url="https://empresa.service-now.com/home",
        )
    )

    assert machine.state == RecordingState.RECORDING


def test_reset_to_idle() -> None:
    machine = RecordingStateMachine(state=RecordingState.ERROR)

    machine.reset_to_idle()

    assert machine.state == RecordingState.IDLE
