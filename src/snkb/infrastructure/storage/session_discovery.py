"""Implementação concreta de ``SessionDiscoveryPort`` (ADR 0014).

Único adaptador autorizado a listar diretórios de sessão exportados —
os módulos centrais nunca leem ``exports/`` diretamente, só escrevem
(Export Engine, ADR 0010). Usa apenas ``pathlib``/Pydantic, nunca
Playwright.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from snkb.application.ports.session_discovery_port import SessionSummary
from snkb.shared.dtos.session_json import SessionJsonModel
from snkb.shared.dtos.statistics_json import StatisticsJsonModel

if TYPE_CHECKING:
    from snkb.application.ports.log_engine_port import LogEnginePort

_SESSION_FILE = "session.json"
_STATISTICS_FILE = "statistics.json"


class DiskSessionDiscovery:
    """Descobre sessões já exportadas em ``output_directory/<session_id>/``.

    Um diretório de sessão malformado ou com ``session.json`` ilegível é
    ignorado (com aviso via ``LogEnginePort``) em vez de derrubar a
    listagem inteira — mesmo princípio já usado pelo Browser Data
    Collector (ADR 0013): um item problemático nunca aborta os demais.
    """

    def __init__(self, output_directory: Path, log_engine: LogEnginePort) -> None:
        self._output_directory = output_directory
        self._log = log_engine

    def list_recent(self, limit: int = 20) -> list[SessionSummary]:
        if not self._output_directory.is_dir():
            return []

        summaries: list[SessionSummary] = []
        for session_dir in self._output_directory.iterdir():
            if not session_dir.is_dir():
                continue
            summary = self._read_session_dir(session_dir)
            if summary is not None:
                summaries.append(summary)

        summaries.sort(key=lambda summary: summary.recording_start, reverse=True)
        return summaries[:limit]

    def find(self, session_id: UUID) -> SessionSummary | None:
        session_dir = self._output_directory / str(session_id)
        if not session_dir.is_dir():
            return None
        return self._read_session_dir(session_dir)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _read_session_dir(self, session_dir: Path) -> SessionSummary | None:
        session_file = session_dir / _SESSION_FILE
        if not session_file.is_file():
            return None

        try:
            session = SessionJsonModel.model_validate_json(session_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            self._log.warning(
                f"Sessão ignorada na descoberta em disco: {error}",
                session_directory=str(session_dir),
            )
            return None

        statistics = self._read_statistics(session_dir, session.recording_id)

        return SessionSummary(
            session_id=session.recording_id,
            status=session.status,
            instance_url=session.instance_url,
            export_directory=session_dir,
            recording_start=session.recording_start,
            recording_end=session.recording_end,
            total_pages=statistics.total_pages if statistics else 0,
            total_elements=statistics.total_elements if statistics else 0,
            total_screenshots=statistics.total_screenshots if statistics else 0,
            error_count=statistics.error_count if statistics else 0,
        )

    def _read_statistics(self, session_dir: Path, session_id: UUID) -> StatisticsJsonModel | None:
        statistics_file = session_dir / _STATISTICS_FILE
        if not statistics_file.is_file():
            return None
        try:
            return StatisticsJsonModel.model_validate_json(
                statistics_file.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            self._log.warning(
                f"Estatísticas ignoradas na descoberta em disco: {error}",
                session_id=str(session_id),
            )
            return None
