"""Comando ``snkb config``.

Depende do Configuration Manager (``infrastructure/configuration``,
ainda reservado — sem implementação) para carregar e exibir a
configuração efetiva da aplicação.
"""

from __future__ import annotations

from snkb.presentation.cli.handlers.pending import announce_pending


def config() -> None:
    """Exibe a configuração efetiva da aplicação."""
    announce_pending("config", "Configuration Manager", "3 (SAD)")
