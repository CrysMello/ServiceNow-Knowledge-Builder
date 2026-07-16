"""Testes de ``RecordCommandHandler`` — o fluxo completo de ``snkb
record`` — usando um ``ApplicationControllerPort`` falso, sem tocar em
Playwright, terminal real ou qualquer módulo ainda não implementado.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from snkb.application.commands.commands import StartCapture, StopCapture
from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.session_events import SessionFailed, SessionStarted
from snkb.presentation.cli.handlers.record_handler import RecordCommandHandler

_INSTANCE_URL = "https://empresa.service-now.com"


class _FakeController:
    """Duplo de teste de ``ApplicationControllerPort``: só registra o
    que foi despachado, sem nenhuma regra de negócio."""

    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, command: object) -> None:
        self.dispatched.append(command)

    def query(self, query: object) -> object:
        raise AssertionError("Não esperado neste teste.")


class _ImmediatelyTriggeredListener:
    """Simula o usuário pressionando Enter assim que o laço começa."""

    def start(self) -> None:
        pass

    @property
    def triggered(self) -> bool:
        return True


class _NeverTriggeredListener:
    """Simula que o usuário nunca pressiona Enter (usado para testar Ctrl+C)."""

    def start(self) -> None:
        pass

    @property
    def triggered(self) -> bool:
        return False


def test_run_dispatches_start_capture_with_given_instance_url() -> None:
    controller = _FakeController()
    handler = RecordCommandHandler(
        controller,
        print_line=lambda _line: None,
        enter_key_listener_factory=_ImmediatelyTriggeredListener,
    )

    handler.run(_INSTANCE_URL)

    assert any(
        isinstance(cmd, StartCapture) and cmd.instance_url == _INSTANCE_URL
        for cmd in controller.dispatched
    )


def test_enter_stops_the_loop_and_dispatches_stop_capture_when_session_started(
    fixed_session_uuid: UUID,
) -> None:
    controller = _FakeController()
    handler = RecordCommandHandler(
        controller,
        print_line=lambda _line: None,
        enter_key_listener_factory=_ImmediatelyTriggeredListener,
    )
    handler.handle_domain_event(SessionStarted(session_id=fixed_session_uuid))

    exit_code = handler.run(_INSTANCE_URL)

    assert exit_code == 0
    assert any(
        isinstance(cmd, StopCapture) and cmd.session_id == fixed_session_uuid
        for cmd in controller.dispatched
    )


def test_no_stop_capture_dispatched_if_session_never_started() -> None:
    controller = _FakeController()
    handler = RecordCommandHandler(
        controller,
        print_line=lambda _line: None,
        enter_key_listener_factory=_ImmediatelyTriggeredListener,
    )

    handler.run(_INSTANCE_URL)

    assert not any(isinstance(cmd, StopCapture) for cmd in controller.dispatched)


def test_ctrl_c_triggers_safe_shutdown_and_dispatches_stop_capture(
    monkeypatch: pytest.MonkeyPatch, fixed_session_uuid: UUID
) -> None:
    controller = _FakeController()
    handler = RecordCommandHandler(
        controller,
        print_line=lambda _line: None,
        enter_key_listener_factory=_NeverTriggeredListener,
    )
    handler.handle_domain_event(SessionStarted(session_id=fixed_session_uuid))

    def _raise_keyboard_interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        "snkb.presentation.cli.handlers.record_handler.time.sleep",
        _raise_keyboard_interrupt,
    )

    exit_code = handler.run(_INSTANCE_URL)

    assert exit_code == 0
    assert any(isinstance(cmd, StopCapture) for cmd in controller.dispatched)


def test_page_captured_events_are_reflected_in_final_output(
    fixed_session_uuid: UUID, fixed_page_uuid: UUID
) -> None:
    controller = _FakeController()
    printed: list[str] = []
    handler = RecordCommandHandler(
        controller,
        print_line=printed.append,
        enter_key_listener_factory=_ImmediatelyTriggeredListener,
    )
    handler.handle_domain_event(SessionStarted(session_id=fixed_session_uuid))
    handler.handle_domain_event(
        PageCaptured(
            session_id=fixed_session_uuid,
            page_id=fixed_page_uuid,
            normalized_url="https://empresa.service-now.com/home",
        )
    )

    handler.run(_INSTANCE_URL)

    assert any("Páginas: 1" in line for line in printed)


def test_printed_lines_never_contain_event_field_content(fixed_session_uuid: UUID) -> None:
    controller = _FakeController()
    printed: list[str] = []
    handler = RecordCommandHandler(
        controller,
        print_line=printed.append,
        enter_key_listener_factory=_ImmediatelyTriggeredListener,
    )
    secret = "conteudo-sensivel-hipotetico"
    handler.handle_domain_event(SessionFailed(session_id=fixed_session_uuid, reason=secret))

    handler.run(_INSTANCE_URL)

    assert not any(secret in line for line in printed)


def test_security_footer_is_always_printed() -> None:
    controller = _FakeController()
    printed: list[str] = []
    handler = RecordCommandHandler(
        controller,
        print_line=printed.append,
        enter_key_listener_factory=_ImmediatelyTriggeredListener,
    )

    handler.run(_INSTANCE_URL)

    assert any(line == "Nenhuma credencial foi armazenada." for line in printed)
