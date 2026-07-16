"""Ponto de entrada da CLI ``snkb`` (registrado em
``pyproject.toml``: ``[project.scripts] snkb = "snkb.presentation.cli.main:main"``).

Apenas registra os 7 subcomandos mínimos exigidos; nenhuma regra de
negócio vive aqui.
"""

from __future__ import annotations

import contextlib
import sys

import typer

from snkb.presentation.cli.commands.config import config
from snkb.presentation.cli.commands.logs import logs
from snkb.presentation.cli.commands.open_folder import open_folder
from snkb.presentation.cli.commands.record import record
from snkb.presentation.cli.commands.status import status
from snkb.presentation.cli.commands.validate import validate
from snkb.presentation.cli.commands.version import version


def _ensure_utf8_stdio() -> None:
    """Garante que stdout/stderr usem UTF-8 mesmo no console legado do
    Windows, que por padrão usa a página de código ativa (sem suporte
    a acentuação). Sem isso, as mensagens em português desta CLI
    apareceriam corrompidas para o usuário — verificado manualmente
    nesta mesma etapa de adequação (compatibilidade com Windows é
    requisito explícito)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8")


_ensure_utf8_stdio()

app = typer.Typer(
    name="snkb",
    help="ServiceNow Knowledge Builder — observa e mapeia sessões do ServiceNow.",
    no_args_is_help=True,
)

app.command(name="record")(record)
app.command(name="status")(status)
app.command(name="validate")(validate)
app.command(name="open")(open_folder)
app.command(name="logs")(logs)
app.command(name="config")(config)
app.command(name="version")(version)


def main() -> None:
    """Executa a aplicação de linha de comando."""
    app()


if __name__ == "__main__":
    main()
