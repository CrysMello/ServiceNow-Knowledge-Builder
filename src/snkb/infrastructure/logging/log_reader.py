"""Implementação concreta de ``LogReaderPort`` (ADR 0014).

Lê os arquivos JSON Lines que ``LoguruLogEngine`` já grava em
``logs/snkb_{time:YYYY-MM-DD}.log`` (``serialize=True``, ADR 0011) e
filtra pelo ``session_id`` que cada módulo central já passa como
contexto (``log_engine.info(..., session_id=str(session_id))`` →
``record.extra.session_id`` via ``logger.bind(**context)``). Único
adaptador autorizado a ler esses arquivos — os módulos centrais nunca
leem seus próprios logs de volta, só escrevem através do
``LogEnginePort``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from snkb.application.ports.log_reader_port import LogRecordSummary

_LOG_FILE_GLOB = "snkb_*.log"


class DiskLogReader:
    """Lê os registros de log persistidos de uma sessão específica."""

    def __init__(self, log_directory: Path) -> None:
        self._log_directory = log_directory

    def read_session_logs(self, session_id: UUID, limit: int = 200) -> list[LogRecordSummary]:
        if not self._log_directory.is_dir():
            return []

        session_id_text = str(session_id)
        matches: list[LogRecordSummary] = []

        for log_file in sorted(self._log_directory.glob(_LOG_FILE_GLOB)):
            for line in self._iter_lines(log_file):
                summary = self._parse_line(line, session_id_text)
                if summary is not None:
                    matches.append(summary)

        matches.sort(key=lambda summary: summary.timestamp, reverse=True)
        return matches[:limit]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _iter_lines(self, log_file: Path) -> list[str]:
        try:
            return log_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []

    def _parse_line(self, line: str, session_id_text: str) -> LogRecordSummary | None:
        stripped = line.strip()
        if not stripped:
            return None
        try:
            payload = json.loads(stripped)
        except ValueError:
            return None

        record = payload.get("record")
        if not isinstance(record, dict):
            return None

        extra = record.get("extra")
        if not isinstance(extra, dict) or extra.get("session_id") != session_id_text:
            return None

        try:
            timestamp = datetime.fromtimestamp(record["time"]["timestamp"], tz=UTC)
            level = str(record["level"]["name"])
            module = str(record["module"])
            message = str(record["message"])
        except (KeyError, TypeError, ValueError, OSError):
            return None

        return LogRecordSummary(timestamp=timestamp, level=level, module=module, message=message)
