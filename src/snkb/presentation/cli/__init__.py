"""Interface de linha de comando (``snkb <comando>``).

Ponto de entrada em ``snkb.presentation.cli.main``. Subpacotes:

- ``commands/``: funções Typer finas, uma por subcomando, sem regra de
  negócio — apenas parsing de argumentos e delegação para ``handlers/``.
- ``handlers/``: orquestração de cada comando, dependendo somente de
  ``ApplicationControllerPort`` (``application.services``).
- ``formatters/``: funções puras que transformam dados/eventos em texto
  de terminal.

``state.py``, ``view_models.py``, ``event_queue.py``,
``state_machine.py`` e ``status_aggregator.py`` não têm nenhuma
dependência de framework de apresentação — poderiam ser reaproveitados
por qualquer front-end futuro, não só pela CLI.
"""
