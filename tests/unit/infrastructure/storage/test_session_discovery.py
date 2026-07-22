"""Testes do ``DiskSessionDiscovery`` (ADR 0014).

Usa o fixture ``tmp_path`` do pytest como ``output_directory`` — nunca
lê ``exports/`` do projeto real. Escreve ``session.json``/
``statistics.json`` diretamente via os DTOs Pydantic já existentes
(mesmos usados pelo Export Engine), sem depender de uma exportação real
de ponta a ponta.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from snkb.infrastructure.storage.session_discovery import DiskSessionDiscovery
from snkb.shared.dtos.session_json import ScreenResolutionModel, SessionJsonModel, ViewportModel
from snkb.shared.dtos.statistics_json import StatisticsJsonModel


class _RecordingLogEngine:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, **context: object) -> None:
        self.warnings.append(message)


def _write_session(
    output_directory: Path,
    session_id: UUID,
    *,
    status: str = "completed",
    recording_start: datetime = datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC),
    with_statistics: bool = True,
) -> Path:
    session_dir = output_directory / str(session_id)
    session_dir.mkdir(parents=True)

    session = SessionJsonModel(
        schema_version="1.0",
        recording_id=session_id,
        instance_url="https://empresa.service-now.com",
        recording_start=recording_start,
        status=status,
        browser="Chromium",
        browser_version="120.0",
        operating_system="Windows",
        screen_resolution=ScreenResolutionModel(width=1920, height=1080),
        viewport=ViewportModel(width=1920, height=1080),
    )
    (session_dir / "session.json").write_text(session.model_dump_json(), encoding="utf-8")

    if with_statistics:
        statistics = StatisticsJsonModel(
            schema_version="1.0",
            session_id=session_id,
            total_pages=3,
            total_elements=10,
            total_screenshots=3,
            error_count=1,
        )
        (session_dir / "statistics.json").write_text(statistics.model_dump_json(), encoding="utf-8")

    return session_dir


def test_list_recent_returns_empty_when_output_directory_missing(tmp_path: Path) -> None:
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path / "missing", log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    assert discovery.list_recent() == []


def test_list_recent_reads_session_and_statistics(tmp_path: Path) -> None:
    session_id = UUID(int=1)
    _write_session(tmp_path, session_id)
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    summaries = discovery.list_recent()

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.session_id == session_id
    assert summary.status == "completed"
    assert summary.total_pages == 3
    assert summary.total_elements == 10
    assert summary.error_count == 1


def test_list_recent_sorts_by_recording_start_descending(tmp_path: Path) -> None:
    older = UUID(int=1)
    newer = UUID(int=2)
    _write_session(tmp_path, older, recording_start=datetime(2026, 1, 1, tzinfo=UTC))
    _write_session(tmp_path, newer, recording_start=datetime(2026, 7, 1, tzinfo=UTC))
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    summaries = discovery.list_recent()

    assert [summary.session_id for summary in summaries] == [newer, older]


def test_list_recent_respects_limit(tmp_path: Path) -> None:
    for index in range(1, 4):
        _write_session(
            tmp_path, UUID(int=index), recording_start=datetime(2026, 1, index, tzinfo=UTC)
        )
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    assert len(discovery.list_recent(limit=2)) == 2


def test_list_recent_ignores_malformed_session_directory(tmp_path: Path) -> None:
    valid_id = UUID(int=1)
    _write_session(tmp_path, valid_id)
    malformed_dir = tmp_path / str(UUID(int=2))
    malformed_dir.mkdir()
    (malformed_dir / "session.json").write_text("not json", encoding="utf-8")
    log_engine = _RecordingLogEngine()
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=log_engine  # type: ignore[arg-type]
    )

    summaries = discovery.list_recent()

    assert [summary.session_id for summary in summaries] == [valid_id]
    assert log_engine.warnings


def test_list_recent_defaults_statistics_to_zero_when_missing(tmp_path: Path) -> None:
    session_id = UUID(int=1)
    _write_session(tmp_path, session_id, with_statistics=False)
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    summary = discovery.list_recent()[0]

    assert summary.total_pages == 0
    assert summary.total_elements == 0
    assert summary.error_count == 0


def test_list_recent_ignores_non_directory_entries(tmp_path: Path) -> None:
    (tmp_path / "stray.txt").write_text("not a session", encoding="utf-8")
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    assert discovery.list_recent() == []


def test_find_returns_matching_session(tmp_path: Path) -> None:
    session_id = UUID(int=1)
    _write_session(tmp_path, session_id)
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    summary = discovery.find(session_id)

    assert summary is not None
    assert summary.session_id == session_id


def test_find_returns_none_when_session_does_not_exist(tmp_path: Path) -> None:
    discovery = DiskSessionDiscovery(
        output_directory=tmp_path, log_engine=_RecordingLogEngine()  # type: ignore[arg-type]
    )

    assert discovery.find(UUID(int=99)) is None
