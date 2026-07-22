"""Comando ``snkb status``.

Descobre a sessão mais recente exportada em disco (ADR 0014) e exibe
seu status e contadores. Função fina: só interpreta a saída da
consulta e delega toda a orquestração ao Application Controller.
"""

from __future__ import annotations

from typing import cast

import typer

from snkb.application.ports.session_discovery_port import SessionSummary
from snkb.application.queries.queries import GetRecentSessions
from snkb.bootstrap import create_controller
from snkb.presentation.cli.formatters.session_summary_formatter import format_session_summary


def status() -> None:
    """Exibe o status e os contadores da sessão de gravação mais recente."""
    try:
        controller = create_controller()
        summaries = cast(list[SessionSummary], controller.query(GetRecentSessions(limit=1)))
    except Exception as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error

    if not summaries:
        typer.echo("Nenhuma sessão encontrada. Grave uma sessão com 'snkb record' antes.")
        raise typer.Exit(code=1)

    typer.echo(format_session_summary(summaries[0]))
