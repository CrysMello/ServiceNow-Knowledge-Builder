"""Composition root: único local autorizado a escolher implementações
concretas para os ports da aplicação (AI Coding Standards, seção 10).

``create_application`` vai eventualmente carregar a configuração,
construir os adaptadores do Log Engine, Browser Manager, Session
Manager, Navigation Recorder, Element Recorder, Selector Analyzer,
Screenshot Engine e Export Engine, ligá-los a uma implementação de
``ApplicationControllerPort`` e entregar esse controller ao UI Manager
(``CustomTkinterUserInterface``, já implementado).

Como nenhum desses adaptadores existe ainda, esta função levanta
``NotImplementedError`` intencionalmente, em vez de devolver uma
aplicação parcialmente ligada e não funcional (PR-007).
"""

from __future__ import annotations

from snkb.presentation.contracts import UserInterfacePort


def create_application() -> UserInterfacePort:
    """Monta todos os adaptadores e retorna o ponto de entrada da UI,
    pronto para rodar.

    Raises:
        NotImplementedError: sempre, até que os módulos listados no AI
            Development Guide (etapas 4-10) sejam implementados. O UI
            Manager (etapa 3) já está pronto em
            ``snkb.presentation.main_window.CustomTkinterUserInterface``,
            mas ainda não há um ``ApplicationControllerPort`` concreto
            para injetar nele.
    """
    raise NotImplementedError(
        "bootstrap.create_application: o UI Manager já está implementado "
        "(snkb.presentation.main_window.CustomTkinterUserInterface), mas "
        "ainda faltam Browser Manager, Session Manager, Navigation "
        "Recorder, Element Recorder, Selector Analyzer, Screenshot "
        "Engine, Export Engine e Log Engine antes de existir um "
        "ApplicationControllerPort concreto para conectar a ela."
    )


def main() -> None:
    """Ponto de entrada da aplicação (invocado por ``python -m snkb``)."""
    application = create_application()
    application.run()


if __name__ == "__main__":
    main()
