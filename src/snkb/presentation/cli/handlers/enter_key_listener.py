"""Escuta a tecla Enter em uma thread auxiliar, sem bloquear o laço
principal de ``snkb record``.

Não é um processo em segundo plano nem um daemon do sistema
operacional: é uma única ``threading.Thread`` do próprio processo do
comando, encerrada junto com ele. Sua única função é chamar uma função
de leitura bloqueante (por padrão, ``input``) e sinalizar um
``threading.Event`` quando ela retornar, para que o laço principal
possa continuar imprimindo o status da gravação enquanto aguarda o
usuário pressionar Enter.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable


class EnterKeyListener:
    """Sinaliza um evento assim que a função de leitura injetada retornar.

    A função de leitura é injetável (em vez de chamar ``input()``
    diretamente) para que os testes possam simular a tecla Enter sem
    bloquear em uma leitura real de stdin.
    """

    def __init__(self, read_line: Callable[[], str] = input) -> None:
        self._read_line = read_line
        self._stopped = threading.Event()
        # `daemon=True` aqui é o conceito de threading da stdlib (a
        # thread não impede o processo de encerrar); não tem relação
        # com um processo daemon do sistema operacional.
        self._thread = threading.Thread(target=self._wait_for_enter, daemon=True)

    def start(self) -> None:
        """Inicia a escuta em segundo plano dentro do próprio processo."""
        self._thread.start()

    @property
    def triggered(self) -> bool:
        """``True`` assim que a função de leitura retornar."""
        return self._stopped.is_set()

    def _wait_for_enter(self) -> None:
        # stdin fechado (ex.: entrada redirecionada) é tratado como um
        # pedido de encerramento em vez de propagar a exceção para uma
        # thread sem tratamento de erro visível ao usuário.
        with contextlib.suppress(EOFError):
            self._read_line()
        self._stopped.set()
