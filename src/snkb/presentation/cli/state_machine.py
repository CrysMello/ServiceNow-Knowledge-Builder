"""Máquina de estados que traduz eventos de domínio consumidos (Module
Specifications, Capítulo 2, seção 2.13) em transições de
``RecordingState`` (2.8, 2.10, 2.11).

Não depende de nenhum framework de apresentação, para que possa ser
testada isoladamente sem terminal nem display (PR-006).
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
from snkb.presentation.cli.state import RecordingState

_STARTABLE_STATES = frozenset(
    {
        RecordingState.IDLE,
        RecordingState.FINISHED,
        RecordingState.ERROR,
        RecordingState.CANCELLED,
        RecordingState.INTERRUPTED,
    }
)
_STOPPABLE_STATES = frozenset({RecordingState.WAITING_LOGIN, RecordingState.RECORDING})


@dataclass(slots=True)
class RecordingStateMachine:
    """Mantém o ``RecordingState`` atual e aplica um evento de domínio
    por vez."""

    state: RecordingState = RecordingState.IDLE

    def apply(self, event: DomainEvent) -> RecordingState:
        """Atualiza e retorna o novo estado para um evento consumido.

        Eventos não reconhecidos não alteram o estado (RNF-022: uma
        falha ao interpretar um evento nunca pode travar a aplicação).
        """
        match event:
            case BrowserStarted():
                self.state = RecordingState.WAITING_LOGIN
            case LoginDetected() | SessionStarted():
                self.state = RecordingState.RECORDING
            case ExportStarted():
                self.state = RecordingState.EXPORTING
            case ExportCompleted():
                self.state = RecordingState.FINISHED
            case ExportFailed() | SessionFailed() | BrowserTimeout() | ErrorOccurred():
                self.state = RecordingState.ERROR
            case BrowserCrashed():
                self.state = RecordingState.INTERRUPTED
        return self.state

    def can_start_capture(self) -> bool:
        """A gravação só pode ser iniciada nestes estados (2.3,
        "Bloquear comandos inválidos")."""
        return self.state in _STARTABLE_STATES

    def can_stop_capture(self) -> bool:
        """A gravação só pode ser parada enquanto há sessão ativa."""
        return self.state in _STOPPABLE_STATES

    def reset_to_idle(self) -> None:
        """Usado quando o login é cancelado (2.11: "retornar ao estado
        Idle")."""
        self.state = RecordingState.IDLE
