"""Máquina de estados que traduz eventos de domínio consumidos (Module
Specifications, Capítulo 2, seção 2.13) em transições de ``UiState``
(2.8, 2.10, 2.11).

Não depende de CustomTkinter nem de nenhum widget, para que possa ser
testada isoladamente sem um display (PR-006).
"""

from __future__ import annotations

from dataclasses import dataclass

from snkb.domain.events.base import DomainEvent
from snkb.domain.events.browser_events import (
    BrowserCrashed,
    BrowserStarted,
    BrowserTimeout,
    LoginDetected,
)
from snkb.domain.events.export_events import ExportCompleted, ExportFailed, ExportStarted
from snkb.domain.events.session_events import SessionFailed, SessionStarted
from snkb.domain.events.system_events import ErrorOccurred
from snkb.presentation.state import UiState

_STARTABLE_STATES = frozenset(
    {
        UiState.IDLE,
        UiState.FINISHED,
        UiState.ERROR,
        UiState.CANCELLED,
        UiState.INTERRUPTED,
    }
)
_STOPPABLE_STATES = frozenset({UiState.WAITING_LOGIN, UiState.RECORDING})


@dataclass(slots=True)
class UiStateMachine:
    """Mantém o ``UiState`` atual e aplica um evento de domínio por vez."""

    state: UiState = UiState.IDLE

    def apply(self, event: DomainEvent) -> UiState:
        """Atualiza e retorna o novo estado para um evento consumido.

        Eventos não reconhecidos não alteram o estado (RNF-022: uma
        falha ao interpretar um evento nunca pode travar a interface).
        """
        match event:
            case BrowserStarted():
                self.state = UiState.WAITING_LOGIN
            case LoginDetected() | SessionStarted():
                self.state = UiState.RECORDING
            case ExportStarted():
                self.state = UiState.EXPORTING
            case ExportCompleted():
                self.state = UiState.FINISHED
            case ExportFailed() | SessionFailed() | BrowserTimeout() | ErrorOccurred():
                self.state = UiState.ERROR
            case BrowserCrashed():
                self.state = UiState.INTERRUPTED
        return self.state

    def can_start_capture(self) -> bool:
        """Botão "Iniciar" só fica habilitado nestes estados (2.3,
        "Bloquear comandos inválidos")."""
        return self.state in _STARTABLE_STATES

    def can_stop_capture(self) -> bool:
        """Botão "Parar" só fica habilitado enquanto há sessão ativa."""
        return self.state in _STOPPABLE_STATES

    def reset_to_idle(self) -> None:
        """Usado quando o login é cancelado (2.11: "retornar ao estado
        Idle")."""
        self.state = UiState.IDLE
