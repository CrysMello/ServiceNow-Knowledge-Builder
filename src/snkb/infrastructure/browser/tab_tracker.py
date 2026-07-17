"""Rastreia as abas (``Page``) abertas dentro de um ``BrowserContext``
(Module Specifications, Capítulo 3, seção 3.9).

Atribui um identificador estável a cada aba e registra os metadados
exigidos (identificador, URL de abertura, horário de abertura/
fechamento). O objeto ``Page`` em si é usado apenas como chave de
dicionário em memória — nunca é copiado para dentro de um
``TabRecord``, e um ``TabRecord`` nunca é exposto como parte de um
evento de domínio (PW-006).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from playwright.async_api import Page


@dataclass(slots=True)
class TabRecord:
    """Metadados de uma aba rastreada, sem nenhuma referência ao
    objeto ``Page`` original."""

    tab_id: str
    opened_at: datetime
    initial_url: str
    closed_at: datetime | None = None


class TabTracker:
    """Associa cada ``Page`` viva a um ``TabRecord``."""

    def __init__(self) -> None:
        self._records: dict[Page, TabRecord] = {}

    def is_tracked(self, page: Page) -> bool:
        return page in self._records

    def register(self, page: Page) -> str:
        """Registra uma nova aba e retorna seu identificador estável.

        Chamar novamente para uma ``page`` já registrada devolve o
        mesmo identificador em vez de criar um registro duplicado.
        """
        existing = self._records.get(page)
        if existing is not None:
            return existing.tab_id

        tab_id = str(uuid4())
        self._records[page] = TabRecord(
            tab_id=tab_id,
            opened_at=datetime.now(UTC),
            initial_url=page.url,
        )
        return tab_id

    def close(self, page: Page) -> str | None:
        """Marca a aba como fechada e retorna seu identificador, ou
        ``None`` se a aba não era rastreada."""
        record = self._records.get(page)
        if record is None:
            return None
        record.closed_at = datetime.now(UTC)
        return record.tab_id

    def tab_id_for(self, page: Page) -> str | None:
        record = self._records.get(page)
        return record.tab_id if record else None

    def open_tabs(self) -> list[TabRecord]:
        """Registros de todas as abas ainda não fechadas."""
        return [record for record in self._records.values() if record.closed_at is None]
