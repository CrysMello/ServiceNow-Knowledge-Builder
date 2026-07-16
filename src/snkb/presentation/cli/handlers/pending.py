"""Mensagem padronizada para comandos que dependem de módulos ainda não
implementados (``status``, ``validate``, ``open``, ``logs``,
``config``).

Centralizado aqui para não duplicar a mesma string, nem o mesmo
tratamento de saída limpa, em cada um dos 5 handlers (AI Coding
Standards, PR-004: "Evitar duplicação de lógica e dados").
"""

from __future__ import annotations

from typing import NoReturn

import typer


def require_module(command_name: str, missing_module: str, chapter: str) -> NoReturn:
    """Levanta ``NotImplementedError`` explicando qual módulo falta.

    Args:
        command_name: nome do subcomando invocado (ex.: ``"status"``).
        missing_module: módulo do qual o comando depende (ex.:
            ``"Session Manager"``).
        chapter: capítulo do Module Specifications que descreve o
            módulo faltante, para referência rápida.

    Raises:
        NotImplementedError: sempre.
    """
    raise NotImplementedError(
        f"snkb {command_name}: este comando depende do {missing_module} "
        f"(Module Specifications, Capítulo {chapter}), que ainda não foi "
        "implementado nesta versão do projeto."
    )


def announce_pending(command_name: str, missing_module: str, chapter: str) -> None:
    """Informa que o comando ainda não está disponível e encerra o
    processo com código de saída 1 e mensagem limpa — nunca um
    traceback bruto."""
    try:
        require_module(command_name, missing_module, chapter)
    except NotImplementedError as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error
