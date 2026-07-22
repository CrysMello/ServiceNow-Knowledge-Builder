"""Comando ``snkb logs``.

Descobre a sessão mais recente exportada em disco (ADR 0014) e lista
seus registros de log persistidos, mais recentes primeiro.
"""

from __future__ import annotations

from typing import cast

import typer

from snkb.application.ports.log_reader_port import LogRecordSummary
from snkb.application.ports.session_discovery_port import SessionSummary
from snkb.application.queries.queries import GetRecentSessions, GetSessionLogs
from snkb.bootstrap import create_controller
from snkb.presentation.cli.formatters.log_formatter import format_log_records


def logs() -> None:
    """Exibe os registros de log da sessão mais recente."""
    try:
        controller = create_controller()
        summaries = cast(list[SessionSummary], controller.query(GetRecentSessions(limit=1)))
    except Exception as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error

    if not summaries:
        typer.echo("Nenhuma sessão encontrada. Grave uma sessão com 'snkb record' antes.")
        raise typer.Exit(code=1)

    records = cast(
        list[LogRecordSummary],
        controller.query(GetSessionLogs(session_id=summaries[0].session_id)),
    )
    typer.echo(format_log_records(records))
