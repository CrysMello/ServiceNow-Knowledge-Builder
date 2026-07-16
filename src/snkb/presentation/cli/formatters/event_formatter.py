"""Formata um evento de domínio como uma linha de terminal.

Apenas o nome da classe do evento é exibido — nunca seus campos —
para nunca vazar um dado sensível que um produtor futuro venha a
colocar em um campo livre como ``reason`` (Module Specifications 2.16,
regra herdada do UI Manager e igualmente aplicável à CLI).
"""

from __future__ import annotations

from snkb.domain.events.base import DomainEvent


def format_event_line(event: DomainEvent) -> str:
    """Uma linha "HH:MM:SS — NomeDoEvento", sem nenhum campo do evento."""
    return f"{event.occurred_at:%H:%M:%S} — {type(event).__name__}"
