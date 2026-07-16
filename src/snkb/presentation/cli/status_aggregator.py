"""Agregação pura dos eventos consumidos durante ``snkb record`` em
contadores exibidos ao usuário (Module Specifications, Capítulo 2,
seção 2.9).

Sem nenhuma dependência de apresentação, para permanecer totalmente
testável.
"""

from __future__ import annotations

from snkb.domain.events.base import DomainEvent
from snkb.domain.events.export_events import ExportFailed
from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.session_events import SessionFailed
from snkb.domain.events.system_events import ErrorOccurred
from snkb.presentation.cli.view_models import RecordingCounters


class RecordingCounterAggregator:
    """Atualiza um ``RecordingCounters`` in-place a cada evento
    consumido.

    Apenas os contadores derivados honestamente dos eventos que a CLI
    está documentada a consumir (2.13) são atualizados aqui.
    """

    def apply(self, counters: RecordingCounters, event: DomainEvent) -> None:
        if isinstance(event, PageCaptured):
            counters.page_count += 1
        elif isinstance(event, ExportFailed | SessionFailed | ErrorOccurred):
            counters.error_count += 1
