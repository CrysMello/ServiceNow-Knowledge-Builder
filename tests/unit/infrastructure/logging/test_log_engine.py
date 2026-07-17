"""Testes do ``LoguruLogEngine`` (Module Specifications, Capítulo 10).

Usa o fixture ``tmp_path`` do pytest como diretório de log — nunca
grava no sistema de arquivos real do projeto. Como o Loguru é rápido e
determinístico (sem processo externo, ao contrário do Playwright), os
testes usam o backend real diretamente, sem duplo de teste.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from snkb.domain.exceptions.log_exceptions import InvalidLogLevelError
from snkb.infrastructure.logging.log_engine import LoguruLogEngine


def _make_engine(
    tmp_path: Path, log_level: str = "trace", retention_days: int = 30
) -> LoguruLogEngine:
    return LoguruLogEngine(
        log_directory=tmp_path,
        log_level=log_level,
        retention_days=retention_days,
        now=lambda: datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC),
    )


# ----------------------------------------------------------------------
# Construção
# ----------------------------------------------------------------------


def test_invalid_log_level_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidLogLevelError):
        LoguruLogEngine(log_directory=tmp_path, log_level="verbose")


def test_log_directory_is_created(tmp_path: Path) -> None:
    log_dir = tmp_path / "nested" / "logs"

    _make_engine(log_dir)

    assert log_dir.is_dir()


# ----------------------------------------------------------------------
# Métodos de log
# ----------------------------------------------------------------------


@pytest.mark.parametrize("level", ["trace", "debug", "info", "warning", "error", "critical"])
def test_each_level_method_records_an_entry(tmp_path: Path, level: str) -> None:
    engine = _make_engine(tmp_path)
    method = getattr(engine, level)

    method("mensagem de teste", session_id="abc-123")

    entries = engine.export()
    assert len(entries) == 1
    assert entries[0]["level"] == level
    assert entries[0]["message"] == "mensagem de teste"
    assert entries[0]["session_id"] == "abc-123"


def test_context_cannot_shadow_the_level_key(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)

    # "message" não pode ser sobrescrito via **context porque já é o
    # parâmetro posicional do método — só "level" (implícito no nome do
    # método) é de fato alcançável através do dicionário de contexto.
    engine.info("mensagem real", level="forjado")

    [entry] = engine.export()
    assert entry["message"] == "mensagem real"
    assert entry["level"] == "info"


def test_exception_is_recorded_at_error_level(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)

    try:
        raise ValueError("falha simulada")
    except ValueError:
        engine.exception("Ocorreu um erro inesperado.")

    [entry] = engine.export()
    assert entry["level"] == "error"
    assert entry["message"] == "Ocorreu um erro inesperado."


# ----------------------------------------------------------------------
# Filtragem por nível
# ----------------------------------------------------------------------


def test_messages_below_configured_level_are_not_recorded(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, log_level="warning")

    engine.trace("nível baixo")
    engine.debug("nível baixo")
    engine.info("nível baixo")
    engine.warning("nível suficiente")
    engine.error("nível suficiente")

    entries = engine.export()
    assert [entry["message"] for entry in entries] == ["nível suficiente", "nível suficiente"]


# ----------------------------------------------------------------------
# flush / export / statistics
# ----------------------------------------------------------------------


def test_flush_does_not_raise_even_without_entries(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)

    engine.flush()


def test_export_returns_independent_copies(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)
    engine.info("primeira mensagem")

    first_export = engine.export()
    first_export[0]["message"] = "adulterado"

    assert engine.export()[0]["message"] == "primeira mensagem"


def test_statistics_aggregates_by_level(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)
    engine.info("a")
    engine.info("b")
    engine.error("c")

    stats = engine.statistics()

    assert stats["total_entries"] == 3
    assert stats["by_level"] == {"info": 2, "error": 1}


# ----------------------------------------------------------------------
# Persistência real via Loguru
# ----------------------------------------------------------------------


def test_log_entries_are_actually_written_to_disk(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)

    engine.info("mensagem persistida", page_id="p-1")
    engine.flush()

    log_files = list(tmp_path.glob("*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")
    assert "mensagem persistida" in content
