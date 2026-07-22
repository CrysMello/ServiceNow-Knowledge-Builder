"""Comando ``snkb validate``.

Descobre a sessão mais recente exportada em disco (ADR 0014) e valida
sua integridade via ``ExportEnginePort.validate()`` (RF-039) — que já
é inteiramente baseado em disco (ADR 0010).
"""

from __future__ import annotations

from typing import cast

import typer

from snkb.application.ports.session_discovery_port import SessionSummary
from snkb.application.queries.queries import GetRecentSessions, ValidateExport
from snkb.bootstrap import create_controller


def validate() -> None:
    """Valida a integridade de uma Base de Conhecimento exportada."""
    try:
        controller = create_controller()
        summaries = cast(list[SessionSummary], controller.query(GetRecentSessions(limit=1)))
    except Exception as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error

    if not summaries:
        typer.echo("Nenhuma sessão encontrada. Grave uma sessão com 'snkb record' antes.")
        raise typer.Exit(code=1)

    session_id = summaries[0].session_id
    is_valid = cast(bool, controller.query(ValidateExport(session_id=session_id)))

    if is_valid:
        typer.echo("Base de Conhecimento válida.")
        return

    typer.echo("Base de Conhecimento inválida — consulte os logs ('snkb logs').", err=True)
    raise typer.Exit(code=1)
