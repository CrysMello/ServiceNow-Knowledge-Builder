"""Agregação pura dos eventos consumidos pelo UI Manager em contadores do
"Painel de Status" (Module Specifications, Capítulo 2, seção 2.9).

Sem nenhum código de widget, para permanecer totalmente testável.
"""

from __future__ import annotations

from snkb.domain.events.base import DomainEvent
from snkb.domain.events.export_events import ExportFailed
from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.session_events import SessionFailed
from snkb.domain.events.system_events import ErrorOccurred
from snkb.presentation.view_models import StatusPanelViewModel


class StatusAggregator:
    """Atualiza um ``StatusPanelViewModel`` in-place a cada evento
    consumido.

    Apenas os contadores derivados honestamente dos eventos que o UI
    Manager está documentado a consumir (2.13) são atualizados aqui.
    """

    def apply(self, view_model: StatusPanelViewModel, event: DomainEvent) -> None:
        if isinstance(event, PageCaptured):
            view_model.page_count += 1
        elif isinstance(event, ExportFailed | SessionFailed | ErrorOccurred):
            view_model.error_count += 1
