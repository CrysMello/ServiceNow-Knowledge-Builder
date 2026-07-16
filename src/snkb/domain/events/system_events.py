"""Eventos transversais, não pertencentes a um único módulo produtor.

``ErrorOccurred`` é publicado por qualquer componente que detecte uma
condição de erro não recuperável (Module Specifications, Capítulo 2,
seção 2.13: "Eventos Consumidos" cita ``ERROR_OCCURRED`` como evento que
o UI Manager consome). Existe aqui, em vez de em um módulo específico,
para que qualquer assinante — incluindo o UI Manager — possa reagir sem
depender de qual módulo efetivamente originou o erro.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.enums.log_level import LogLevel
from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorOccurred(DomainEvent):
    """Erro genérico reportado por qualquer módulo da aplicação.

    ``session_id`` é opcional porque alguns erros (ex.: falha ao
    inicializar o Playwright) podem ocorrer antes de existir uma sessão.
    """

    session_id: UUID | None
    module: str
    message: str
    severity: LogLevel = LogLevel.ERROR
