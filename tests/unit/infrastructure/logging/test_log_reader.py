"""Testes do ``DiskLogReader`` (ADR 0014).

Usa o ``LoguruLogEngine`` real (``enqueue=False``, escreve de forma
síncrona) para gravar os arquivos ``logs/snkb_*.log`` de verdade em
``tmp_path`` — evita reimplementar à mão o formato JSON Lines do
Loguru (``serialize=True``), que só o backend real garante estar
correto.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from snkb.infrastructure.logging.log_engine import LoguruLogEngine
from snkb.infrastructure.logging.log_reader import DiskLogReader


def test_read_session_logs_returns_empty_when_directory_missing(tmp_path: Path) -> None:
    reader = DiskLogReader(log_directory=tmp_path / "missing")

    assert reader.read_session_logs(UUID(int=1)) == []


def test_read_session_logs_filters_by_session_id(tmp_path: Path) -> None:
    engine = LoguruLogEngine(log_directory=tmp_path)
    session_id = UUID(int=1)
    other_session_id = UUID(int=2)

    engine.info("Sessão iniciada.", session_id=str(session_id))
    engine.warning("Aviso da outra sessão.", session_id=str(other_session_id))
    engine.error("Falha na sessão.", session_id=str(session_id))
    engine.flush()

    reader = DiskLogReader(log_directory=tmp_path)
    records = reader.read_session_logs(session_id)

    assert len(records) == 2
    assert all(True for _ in records)  # sanidade: nenhuma exceção ao iterar
    messages = {record.message for record in records}
    assert messages == {"Sessão iniciada.", "Falha na sessão."}


def test_read_session_logs_orders_most_recent_first(tmp_path: Path) -> None:
    engine = LoguruLogEngine(log_directory=tmp_path)
    session_id = UUID(int=1)

    engine.info("primeira", session_id=str(session_id))
    engine.info("segunda", session_id=str(session_id))
    engine.flush()

    reader = DiskLogReader(log_directory=tmp_path)
    records = reader.read_session_logs(session_id)

    assert [record.message for record in records] == ["segunda", "primeira"]


def test_read_session_logs_respects_limit(tmp_path: Path) -> None:
    engine = LoguruLogEngine(log_directory=tmp_path)
    session_id = UUID(int=1)
    for index in range(5):
        engine.info(f"mensagem {index}", session_id=str(session_id))
    engine.flush()

    reader = DiskLogReader(log_directory=tmp_path)

    assert len(reader.read_session_logs(session_id, limit=2)) == 2


def test_read_session_logs_ignores_records_without_session_id(tmp_path: Path) -> None:
    engine = LoguruLogEngine(log_directory=tmp_path)
    engine.info("sem contexto de sessão")
    engine.flush()

    reader = DiskLogReader(log_directory=tmp_path)

    assert reader.read_session_logs(UUID(int=1)) == []


def test_read_session_logs_ignores_malformed_lines(tmp_path: Path) -> None:
    log_file = tmp_path / "snkb_2026-07-21.log"
    log_file.write_text("not json at all\n", encoding="utf-8")

    reader = DiskLogReader(log_directory=tmp_path)

    assert reader.read_session_logs(UUID(int=1)) == []
