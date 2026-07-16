"""Comando ``snkb status``.

Depende do Session Manager (Module Specifications, Capítulo 4) para
consultar o estado e as estatísticas da sessão mais recente — módulo
ainda não implementado.
"""

from __future__ import annotations

from snkb.presentation.cli.handlers.pending import announce_pending


def status() -> None:
    """Exibe o status e os contadores da sessão de gravação mais recente."""
    announce_pending("status", "Session Manager", "4")
