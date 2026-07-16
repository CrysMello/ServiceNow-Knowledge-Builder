"""Orquestra o comando ``snkb record`` (Module Specifications, Capítulo
2, seção 2.10 — fluxo adaptado de GUI para terminal).

Fluxo: dispatch ``StartCapture`` -> aguarda login/gravação (eventos de
domínio consumidos via ``DomainEventQueue``) -> mantém captura ativa,
imprimindo status -> aguarda Enter (``EnterKeyListener``) ou
``KeyboardInterrupt`` (Ctrl+C) -> dispatch ``StopCapture`` -> aguarda
``ExportCompleted``/``ExportFailed`` -> exibe o caminho da Base de
Conhecimento (ou o erro).

Não implementa processo em segundo plano, daemon do sistema
operacional, socket local ou gerenciamento de PID: tudo roda em
foreground, no próprio processo de ``snkb record``, com uma única
thread auxiliar (``EnterKeyListener``) apenas para não bloquear o laço
de status enquanto aguarda ``input()``.

Este handler assume que ``controller`` já é um ``ApplicationControllerPort``
válido — a falha em construí-lo (``NotImplementedError`` de
``bootstrap.create_controller``, hoje sempre levantada, pois nenhum
módulo central existe ainda) é tratada por quem chama este handler
(``commands/record.py``), não aqui.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from snkb.application.commands.commands import StartCapture, StopCapture
from snkb.domain.events.base import DomainEvent
from snkb.domain.events.export_events import ExportCompleted, ExportFailed
from snkb.domain.events.session_events import SessionStarted
from snkb.presentation.cli.event_queue import DomainEventQueue
from snkb.presentation.cli.formatters.event_formatter import format_event_line
from snkb.presentation.cli.formatters.session_formatter import format_session_info
from snkb.presentation.cli.formatters.status_formatter import (
    SECURITY_FOOTER_TEXT,
    format_status_message,
)
from snkb.presentation.cli.handlers.enter_key_listener import EnterKeyListener
from snkb.presentation.cli.state import RecordingState
from snkb.presentation.cli.state_machine import RecordingStateMachine
from snkb.presentation.cli.status_aggregator import RecordingCounterAggregator
from snkb.presentation.cli.view_models import RecordingCounters, SessionInfo

if TYPE_CHECKING:
    from snkb.application.services.application_controller_port import (
        ApplicationControllerPort,
    )

# Intervalo do laço de status enquanto aguarda Enter/eventos (2.15: a
# atualização de contadores deve ser percebida em tempo próximo do real).
_POLL_INTERVAL_SECONDS = 0.2

_STOPPING_STATES = frozenset({RecordingState.ERROR, RecordingState.INTERRUPTED})


class RecordCommandHandler:
    """Orquestra o fluxo completo de ``snkb record`` em foreground."""

    def __init__(
        self,
        controller: ApplicationControllerPort,
        print_line: Callable[[str], None] = print,
        enter_key_listener_factory: Callable[[], EnterKeyListener] = EnterKeyListener,
    ) -> None:
        self._controller = controller
        self._print_line = print_line
        self._enter_key_listener_factory = enter_key_listener_factory

        self._state_machine = RecordingStateMachine()
        self._counter_aggregator = RecordingCounterAggregator()
        self._event_queue = DomainEventQueue()
        self._session = SessionInfo()
        self._counters = RecordingCounters()
        self._recording_started_at: datetime | None = None
        self._export_directory: str | None = None
        self._export_failed_reason: str | None = None

    def handle_domain_event(self, event: DomainEvent) -> None:
        """Ponto de entrada thread-safe para eventos publicados fora da
        thread principal (ASY-006). Apenas enfileira; o processamento
        real ocorre no laço principal de ``run``."""
        self._event_queue.submit(event)

    def run(self, instance_url: str) -> int:
        """Executa o comando e retorna o código de saída do processo."""
        self._print_line("Inicializando aplicação...")
        self._controller.dispatch(StartCapture(instance_url=instance_url))

        self._state_machine.state = RecordingState.STARTING
        self._print_line(format_status_message(self._state_machine.state, 0))

        listener = self._enter_key_listener_factory()
        listener.start()
        self._print_line("Pressione Enter para encerrar a gravação com segurança.")

        try:
            self._run_loop_until_stop_requested(listener)
        except KeyboardInterrupt:
            self._print_line("\nInterrupção recebida (Ctrl+C). Encerrando com segurança...")

        return self._finalize()

    def _run_loop_until_stop_requested(self, listener: EnterKeyListener) -> None:
        while True:
            self._drain_and_process_events()
            self._update_elapsed_time()

            if listener.triggered or self._state_machine.state in _STOPPING_STATES:
                return

            time.sleep(_POLL_INTERVAL_SECONDS)

    def _drain_and_process_events(self) -> None:
        for event in self._event_queue.drain():
            if isinstance(event, SessionStarted):
                self._session.session_id = event.session_id
                self._recording_started_at = datetime.now(UTC)
            elif isinstance(event, ExportCompleted):
                self._export_directory = event.output_directory
            elif isinstance(event, ExportFailed):
                self._export_failed_reason = event.reason

            self._state_machine.apply(event)
            self._counter_aggregator.apply(self._counters, event)
            self._print_line(format_event_line(event))

    def _update_elapsed_time(self) -> None:
        if self._recording_started_at is None:
            return
        self._counters.elapsed_seconds = (
            datetime.now(UTC) - self._recording_started_at
        ).total_seconds()

    def _finalize(self) -> int:
        if self._state_machine.can_stop_capture() and self._session.session_id is not None:
            self._print_line(format_status_message(RecordingState.EXPORTING, 0))
            self._controller.dispatch(StopCapture(session_id=self._session.session_id))
            self._drain_and_process_events()

        self._print_line(format_session_info(self._session, self._counters))
        self._print_line(
            format_status_message(self._state_machine.state, self._counters.error_count)
        )
        self._print_line(SECURITY_FOOTER_TEXT)

        if self._export_directory is not None:
            self._print_line(f"Base de Conhecimento exportada em: {self._export_directory}")
            return 0
        if self._export_failed_reason is not None:
            self._print_line(f"Falha na exportação: {self._export_failed_reason}")
            return 1
        return 0
