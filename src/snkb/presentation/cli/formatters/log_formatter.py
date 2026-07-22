"""Formata registros de log persistidos (``LogRecordSummary``, ADR
0014) em texto de terminal para ``snkb logs``."""

from __future__ import annotations

from snkb.application.ports.log_reader_port import LogRecordSummary

_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_log_records(records: list[LogRecordSummary]) -> str:
    """Uma linha por registro, mais recente primeiro (mesma ordem em
    que ``LogReaderPort.read_session_logs`` já devolve)."""
    if not records:
        return "Nenhum registro de log encontrado para esta sessão."
    lines = [
        f"{record.timestamp.strftime(_DATETIME_FORMAT)} [{record.level}] "
        f"{record.module}: {record.message}"
        for record in records
    ]
    return "\n".join(lines)
