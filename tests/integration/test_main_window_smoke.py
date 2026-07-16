"""Teste de fumaça: a janela CustomTkinter real deve construir, receber
um evento de domínio e encerrar sem erros.

Requer um display gráfico. Em ambiente sem display (ex.: CI headless
sem Xvfb), o teste é pulado em vez de falhar — a lógica pura do UI
Manager (estado, contadores, fila de eventos) já é coberta pelos testes
unitários em ``tests/unit/presentation``.

A janela é construída uma única vez por módulo (``scope="module"``):
instanciar mais de um ``ctk.CTk()`` raiz por processo é uma fonte
conhecida de instabilidade no Tkinter. Cada teste recebe um fixture de
função que apenas reseta o estado observável antes de rodar, para
permanecer independente da ordem de execução.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest

from snkb.application.commands.commands import StartCapture, StopCapture
from snkb.domain.events.session_events import SessionStarted
from snkb.presentation.main_window import CustomTkinterUserInterface
from snkb.presentation.state import UiState
from snkb.presentation.view_models import SessionPanelViewModel, StatusPanelViewModel


class _RecordingController:
    """Duplo de teste de ``ApplicationControllerPort``: apenas registra
    o que foi despachado, sem executar nenhuma regra de negócio."""

    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, command: object) -> None:
        self.dispatched.append(command)

    def query(self, query: object) -> object:
        raise AssertionError("Não esperado neste teste de fumaça.")


@pytest.fixture(scope="module")
def ui_environment() -> Iterator[tuple[CustomTkinterUserInterface, _RecordingController]]:
    controller = _RecordingController()
    try:
        ui = CustomTkinterUserInterface(
            controller=controller, instance_url="https://empresa.service-now.com"
        )
    except Exception as error:  # noqa: BLE001 — ambiente sem display gráfico.
        pytest.skip(f"Sem display gráfico disponível para o teste de UI: {error}")
    yield ui, controller
    ui.shutdown()


@pytest.fixture
def window(
    ui_environment: tuple[CustomTkinterUserInterface, _RecordingController],
) -> tuple[CustomTkinterUserInterface, _RecordingController]:
    ui, controller = ui_environment
    controller.dispatched.clear()
    ui._state_machine.state = UiState.IDLE  # noqa: SLF001
    ui._session = SessionPanelViewModel()  # noqa: SLF001
    ui._status = StatusPanelViewModel()  # noqa: SLF001
    ui._recording_started_at = None  # noqa: SLF001
    return ui, controller


def test_start_button_dispatches_start_capture(
    window: tuple[CustomTkinterUserInterface, _RecordingController],
) -> None:
    ui, controller = window

    ui._on_start_clicked()  # noqa: SLF001 — acesso interno intencional em teste de fumaça.

    assert any(isinstance(cmd, StartCapture) for cmd in controller.dispatched)


def test_stop_button_is_noop_without_active_session(
    window: tuple[CustomTkinterUserInterface, _RecordingController],
) -> None:
    ui, controller = window

    ui._on_stop_clicked()  # noqa: SLF001

    assert not any(isinstance(cmd, StopCapture) for cmd in controller.dispatched)


def test_handle_domain_event_updates_state_after_polling(
    window: tuple[CustomTkinterUserInterface, _RecordingController],
    fixed_session_uuid: UUID,
) -> None:
    ui, _controller = window

    ui.handle_domain_event(SessionStarted(session_id=fixed_session_uuid))
    ui._poll_events()  # noqa: SLF001

    assert ui._state_machine.state == UiState.RECORDING  # noqa: SLF001
    assert ui._session.session_id == fixed_session_uuid  # noqa: SLF001
