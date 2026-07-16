"""Comando ``snkb open``.

Arquivo nomeado ``open_folder.py`` (não ``open.py``) para não colidir
com a função builtin ``open``; o subcomando registrado em
``presentation.cli.main`` continua se chamando ``open``.

Depende do Export Engine (Module Specifications, Capítulo 9) para
localizar o diretório de exportação da sessão mais recente — módulo
ainda não implementado.
"""

from __future__ import annotations

from snkb.presentation.cli.handlers.pending import announce_pending


def open_folder() -> None:
    """Abre no explorador de arquivos a pasta de exportação da sessão
    mais recente."""
    announce_pending("open", "Export Engine", "9")
