"""Ponte thread-safe entre produtores de eventos em segundo plano
(futuras tasks assíncronas do Browser Manager/Session Manager) e a
thread principal do comando ``snkb record``.

AI Coding Standards, ASY-006: "Atualizações da UI serão encaminhadas
por canal seguro para a thread principal" — na CLI, a "thread
principal" é o laço de polling do ``RecordCommandHandler``, e não mais
o ``after()`` de um toolkit gráfico, mas a regra permanece: ``submit``
pode ser chamado de qualquer thread; ``drain`` só deve ser chamado a
partir da thread que processa e imprime os eventos.
"""

from __future__ import annotations

import queue

from snkb.domain.events.base import DomainEvent


class DomainEventQueue:
    """Fila FIFO de eventos de domínio pendentes de processamento."""

    def __init__(self) -> None:
        self._queue: queue.Queue[DomainEvent] = queue.Queue()

    def submit(self, event: DomainEvent) -> None:
        """Enfileira um evento. Seguro para chamar de qualquer thread."""
        self._queue.put_nowait(event)

    def drain(self) -> list[DomainEvent]:
        """Remove e retorna todos os eventos pendentes, na ordem de chegada.

        Deve ser chamado apenas pela thread que consome os eventos.
        """
        events: list[DomainEvent] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events
