"""Implementação concreta de ``FolderOpenerPort`` (ADR 0014).

Windows é a plataforma alvo do projeto (ver o tratamento de UTF-8 do
console em ``presentation/cli/main.py``); ``os.startfile`` é usado
nesse caso. O fallback via ``subprocess`` existe apenas para não
quebrar a suíte de testes em CI não-Windows — nunca foi validado como
fluxo principal do produto.
"""

from __future__ import annotations

import subprocess  # noqa: S404 - only used to open a folder, never user input
import sys
from pathlib import Path


class OsFolderOpener:
    """Abre um diretório no explorador de arquivos do sistema
    operacional."""

    def open(self, path: Path) -> None:
        if sys.platform == "win32":
            import os

            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
