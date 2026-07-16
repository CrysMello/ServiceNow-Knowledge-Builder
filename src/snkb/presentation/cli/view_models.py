"""Modelos de dados exibidos pela CLI durante ``snkb record`` (Module
Specifications, Capítulo 2, seção 2.9 — adaptado de painéis de GUI para
blocos de texto de terminal).

São apenas dados: nenhuma classe aqui interpreta regras de negócio,
acessa o navegador ou grava arquivos (2.4, "Responsabilidades
Proibidas"). Os valores são preenchidos a partir dos eventos de domínio
consumidos e, futuramente, de consultas ao Session Manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from snkb.presentation.cli.state import RecordingState


@dataclass(slots=True)
class SessionInfo:
    """Dados de identificação da sessão em andamento."""

    session_id: UUID | None = None
    started_at: datetime | None = None
    user: str | None = None
    instance: str | None = None
    language: str | None = None
    resolution: str | None = None
    browser: str | None = None


@dataclass(slots=True)
class RecordingCounters:
    """Contadores exibidos durante a gravação.

    ``element_count``, ``screenshot_count`` e ``log_count`` permanecem
    em zero até que o Element Recorder, o Screenshot Engine e o Log
    Engine publiquem eventos que a CLI possa consumir — exibir um valor
    não derivado de um evento real violaria a responsabilidade deste
    módulo de apenas repassar o que foi observado.
    """

    status: RecordingState = RecordingState.IDLE
    elapsed_seconds: float = 0.0
    page_count: int = 0
    element_count: int = 0
    screenshot_count: int = 0
    log_count: int = 0
    error_count: int = 0


@dataclass(frozen=True, slots=True)
class LogEntry:
    """Uma linha de log exibida pelo comando ``snkb logs``."""

    timestamp: datetime
    level: str
    module: str
    message: str
