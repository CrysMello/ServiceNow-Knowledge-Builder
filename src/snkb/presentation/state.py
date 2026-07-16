"""Estados do ciclo de vida da interface (Module Specifications, Capítulo
2, seções 2.8 e 2.11)."""

from __future__ import annotations

from enum import StrEnum


class UiState(StrEnum):
    """Estado atualmente exibido pelo UI Manager.

    ``CANCELLED`` e ``INTERRUPTED`` cobrem os fluxos alternativos da
    seção 2.11 ("Login cancelado" e "Browser encerrado manualmente"),
    que não aparecem na lista principal de estados da seção 2.8 mas são
    estados visuais distintos exigidos pelos critérios de aceite (2.17).
    """

    IDLE = "idle"
    STARTING = "starting"
    WAITING_LOGIN = "waiting_login"
    RECORDING = "recording"
    EXPORTING = "exporting"
    FINISHED = "finished"
    ERROR = "error"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
