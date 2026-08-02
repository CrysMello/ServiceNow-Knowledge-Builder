"""Agregação pura dos eventos consumidos durante ``snkb record`` em
contadores exibidos ao usuário (Module Specifications, Capítulo 2,
seção 2.9).

Sem nenhuma dependência de apresentação, para permanecer totalmente
testável.
"""

from __future__ import annotations

from uuid import UUID

from snkb.domain.events.base import DomainEvent
from snkb.domain.events.element_events import ElementsCaptured
from snkb.domain.events.export_events import ExportFailed
from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.screenshot_events import ScreenshotCreated
from snkb.domain.events.session_events import SessionFailed
from snkb.domain.events.system_events import ErrorOccurred
from snkb.presentation.cli.view_models import RecordingCounters


class RecordingCounterAggregator:
    """Atualiza um ``RecordingCounters`` in-place a cada evento
    consumido.

    Apenas os contadores derivados honestamente dos eventos que a CLI
    está documentada a consumir (2.13) são atualizados aqui.
    """

    def __init__(self) -> None:
        # ElementsCaptured.element_count é cumulativo por página (o
        # Element Recorder pode recapturar a mesma página várias vezes
        # conforme o DOM muda), então somamos o último valor conhecido
        # de cada página em vez de somar cada evento recebido.
        self._element_counts_by_page: dict[UUID, int] = {}

    def apply(self, counters: RecordingCounters, event: DomainEvent) -> None:
        if isinstance(event, PageCaptured):
            counters.page_count += 1
        elif isinstance(event, ElementsCaptured):
            self._element_counts_by_page[event.page_id] = event.element_count
            counters.element_count = sum(self._element_counts_by_page.values())
        elif isinstance(event, ScreenshotCreated):
            counters.screenshot_count += 1
        elif isinstance(event, ExportFailed | SessionFailed | ErrorOccurred):
            counters.error_count += 1
