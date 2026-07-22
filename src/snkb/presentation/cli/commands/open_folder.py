"""Comando ``snkb open``.

Arquivo nomeado ``open_folder.py`` (não ``open.py``) para não colidir
com a função builtin ``open``; o subcomando registrado em
``presentation.cli.main`` continua se chamando ``open``.

Descobre a sessão mais recente exportada em disco (ADR 0014) e
despacha ``OpenExportFolder`` para o Application Controller abrir seu
diretório de exportação no explorador de arquivos do sistema
operacional.
"""

from __future__ import annotations

from typing import cast

import typer

from snkb.application.commands.commands import OpenExportFolder
from snkb.application.ports.session_discovery_port import SessionSummary
from snkb.application.queries.queries import GetRecentSessions
from snkb.bootstrap import create_controller


def open_folder() -> None:
    """Abre no explorador de arquivos a pasta de exportação da sessão
    mais recente."""
    try:
        controller = create_controller()
        summaries = cast(list[SessionSummary], controller.query(GetRecentSessions(limit=1)))
    except Exception as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error

    if not summaries:
        typer.echo("Nenhuma sessão encontrada. Grave uma sessão com 'snkb record' antes.")
        raise typer.Exit(code=1)

    controller.dispatch(OpenExportFolder(session_id=summaries[0].session_id))
