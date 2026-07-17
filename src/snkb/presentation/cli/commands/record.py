"""Comando ``snkb record`` (MVP — Module Specifications, Capítulo 2,
seção 2.10).

Função fina: só interpreta a opção de linha de comando e delega toda a
orquestração para ``RecordCommandHandler``. Nenhuma regra de negócio
vive aqui.
"""

from __future__ import annotations

import typer

from snkb.bootstrap import create_controller
from snkb.presentation.cli.handlers.record_handler import RecordCommandHandler


def record(
    instance_url: str = typer.Option(
        ...,
        "--instance-url",
        help="URL da instância ServiceNow a observar (ex.: https://empresa.service-now.com).",
    ),
) -> None:
    """Inicia uma nova sessão de gravação e observa a navegação até que
    o usuário pressione Enter ou interrompa com Ctrl+C."""
    try:
        controller = create_controller()
    except Exception as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error

    handler = RecordCommandHandler(controller)
    controller.subscribe(handler.handle_domain_event)
    exit_code = handler.run(instance_url)
    raise typer.Exit(code=exit_code)
