"""Comando ``snkb config``.

Exibe a configuração efetiva carregada pelo Configuration Manager
(``infrastructure/configuration/configuration_manager.py``, ADR 0015).
"""

from __future__ import annotations

from typing import cast

import typer

from snkb.application.queries.queries import GetEffectiveConfiguration
from snkb.bootstrap import create_controller
from snkb.presentation.cli.formatters.config_formatter import format_config
from snkb.shared.dtos.app_config import AppConfig


def config() -> None:
    """Exibe a configuração efetiva da aplicação."""
    try:
        controller = create_controller()
        effective_config = cast(AppConfig, controller.query(GetEffectiveConfiguration()))
    except Exception as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(format_config(effective_config))
