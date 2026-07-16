"""Composition root: único local autorizado a escolher implementações
concretas para os ports da aplicação (AI Coding Standards, seção 10).

``create_controller`` vai eventualmente carregar a configuração,
construir os adaptadores do Log Engine, Browser Manager, Session
Manager, Navigation Recorder, Element Recorder, Selector Analyzer,
Screenshot Engine e Export Engine, e ligá-los a uma implementação de
``ApplicationControllerPort``. O ponto de entrada real da aplicação é a
CLI (``snkb.presentation.cli.main:main``, registrado em
``[project.scripts]``), que injeta o controller retornado aqui em cada
handler de comando (ver ADR 0003).

Como nenhum desses adaptadores existe ainda, esta função levanta
``NotImplementedError`` intencionalmente, em vez de devolver um
controller parcialmente ligado e não funcional (PR-007).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snkb.application.services.application_controller_port import (
        ApplicationControllerPort,
    )


def create_controller() -> ApplicationControllerPort:
    """Monta todos os adaptadores e retorna o ``ApplicationControllerPort``
    pronto para uso pelos comandos da CLI.

    Raises:
        NotImplementedError: sempre, até que os módulos listados no AI
            Development Guide (etapas 4-10) sejam implementados: Browser
            Manager, Session Manager, Navigation Recorder, Element
            Recorder, Selector Analyzer, Screenshot Engine, Export
            Engine e Log Engine.
    """
    raise NotImplementedError(
        "snkb: nenhum módulo central foi implementado ainda (Browser "
        "Manager, Session Manager, Navigation Recorder, Element "
        "Recorder, Selector Analyzer, Screenshot Engine, Export Engine "
        "e Log Engine). bootstrap.create_controller não pode montar um "
        "ApplicationControllerPort funcional até que pelo menos esses "
        "módulos existam."
    )
