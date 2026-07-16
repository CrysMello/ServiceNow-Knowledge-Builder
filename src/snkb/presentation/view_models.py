"""Modelos de exibição (read models) dos painéis do UI Manager (Module
Specifications, Capítulo 2, seção 2.9).

São apenas dados: nenhuma classe aqui interpreta regras de negócio,
acessa o navegador ou grava arquivos (2.4, "Responsabilidades
Proibidas"). Os valores são preenchidos a partir dos eventos de domínio
consumidos e, futuramente, de consultas ao Session Manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from snkb.presentation.state import UiState


@dataclass(slots=True)
class SessionPanelViewModel:
    """Dados exibidos no "Painel da Sessão" (2.9)."""

    session_id: UUID | None = None
    started_at: datetime | None = None
    user: str | None = None
    instance: str | None = None
    language: str | None = None
    resolution: str | None = None
    browser: str | None = None


@dataclass(slots=True)
class StatusPanelViewModel:
    """Contadores exibidos no "Painel de Status" (2.9).

    ``element_count``, ``screenshot_count`` e ``log_count`` permanecem
    em zero até que o Element Recorder, o Screenshot Engine e o Log
    Engine publiquem eventos que o UI Manager possa consumir — exibir um
    valor não derivado de um evento real violaria a responsabilidade do
    módulo de apenas repassar o que foi observado.
    """

    status: UiState = UiState.IDLE
    elapsed_seconds: float = 0.0
    page_count: int = 0
    element_count: int = 0
    screenshot_count: int = 0
    log_count: int = 0
    error_count: int = 0


@dataclass(frozen=True, slots=True)
class LogEntryViewModel:
    """Uma linha do "Painel de Logs" (2.9)."""

    timestamp: datetime
    level: str
    module: str
    message: str
