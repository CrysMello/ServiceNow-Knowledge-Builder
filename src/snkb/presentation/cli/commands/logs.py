"""Comando ``snkb logs``.

Depende do Log Engine (Module Specifications, Capítulo 10) para listar
os registros de uma sessão — módulo ainda não implementado.
"""

from __future__ import annotations

from snkb.presentation.cli.handlers.pending import announce_pending


def logs() -> None:
    """Exibe os registros de log da sessão mais recente."""
    announce_pending("logs", "Log Engine", "10")
