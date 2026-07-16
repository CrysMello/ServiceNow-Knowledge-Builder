"""Comando ``snkb version``.

Único comando sem dependência de ``ApplicationControllerPort``: a
versão vem diretamente do pacote instalado.
"""

from __future__ import annotations

import typer

from snkb import __version__


def version() -> None:
    """Exibe a versão instalada do ServiceNow Knowledge Builder."""
    typer.echo(f"ServiceNow Knowledge Builder v{__version__}")
