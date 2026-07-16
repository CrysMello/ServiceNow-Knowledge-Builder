"""Contrato público do UI Manager (Module Specifications, Capítulo 2).

A implementação concreta em CustomTkinter vive em
``snkb.presentation.main_window.CustomTkinterUserInterface``.
"""

from __future__ import annotations

from typing import Protocol

from snkb.domain.events.base import DomainEvent


class UserInterfacePort(Protocol):
    """Ponto de entrada da interface gráfica.

    Recebe uma única instância de ``ApplicationControllerPort`` na
    construção (ARQ-002) e nunca acessa managers de infraestrutura
    diretamente (Module Specifications 2.5).
    """

    def run(self) -> None: ...
    def shutdown(self) -> None: ...

    def handle_domain_event(self, event: DomainEvent) -> None:
        """Recebe um evento de domínio publicado por qualquer módulo.

        Deve ser seguro chamar a partir de qualquer thread (ASY-006): a
        implementação apenas enfileira o evento e o processa na thread
        principal da interface.
        """
        ...
