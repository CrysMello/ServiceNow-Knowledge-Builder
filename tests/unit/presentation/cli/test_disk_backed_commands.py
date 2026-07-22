"""Testes de ``snkb status``/``validate``/``open``/``logs`` via
``typer.testing.CliRunner`` (ADR 0014).

Cada comando descobre "a sessão mais recente" lendo
``exports/<session_id>/`` — estes testes escrevem esses artefatos
diretamente em ``tmp_path`` (via ``monkeypatch.chdir``), sem depender
de uma gravação real com Chromium (já coberta por
``tests/acceptance/test_local_recording_flow.py`` e
``tests/integration/test_application_controller_integration.py``).

``open`` nunca deve abrir uma janela real do explorador de arquivos
durante a suíte: ``os.startfile`` é substituído por um duplo em todo
teste que exercita esse comando.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

import pytest
from typer.testing import CliRunner

from snkb.infrastructure.logging.log_engine import LoguruLogEngine
from snkb.presentation.cli.main import app
from snkb.shared.dtos.session_json import ScreenResolutionModel, SessionJsonModel, ViewportModel

runner = CliRunner()

_CONFIG_PAYLOAD = {
    "instance_url": "https://empresa.service-now.com",
    "output_directory": "exports",
}


@pytest.fixture(autouse=True)
def _chdir_with_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.json").write_text(json.dumps(_CONFIG_PAYLOAD), encoding="utf-8")
    monkeypatch.chdir(tmp_path)


def _write_session(tmp_path: Path, session_id: UUID) -> Path:
    session_dir = tmp_path / "exports" / str(session_id)
    session_dir.mkdir(parents=True)
    session = SessionJsonModel(
        schema_version="1.0",
        recording_id=session_id,
        instance_url="https://empresa.service-now.com",
        recording_start="2026-07-17T09:00:00Z",  # type: ignore[arg-type]
        status="completed",
        browser="Chromium",
        browser_version="120.0",
        operating_system="Windows",
        screen_resolution=ScreenResolutionModel(width=1920, height=1080),
        viewport=ViewportModel(width=1920, height=1080),
    )
    (session_dir / "session.json").write_text(session.model_dump_json(), encoding="utf-8")
    return session_dir


# ----------------------------------------------------------------------
# status
# ----------------------------------------------------------------------


def test_status_reports_no_session_found() -> None:
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    assert "Nenhuma sessão encontrada" in result.output


def test_status_shows_the_most_recent_session(tmp_path: Path) -> None:
    session_id = UUID(int=1)
    _write_session(tmp_path, session_id)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert str(session_id) in result.output
    assert "completed" in result.output


# ----------------------------------------------------------------------
# validate
# ----------------------------------------------------------------------


def test_validate_reports_no_session_found() -> None:
    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 1
    assert "Nenhuma sessão encontrada" in result.output


def test_validate_reports_invalid_export_for_incomplete_session(tmp_path: Path) -> None:
    # session.json existe, mas navigation.json/selectors.json/etc. não —
    # export_engine.validate() deve honestamente reportar inválido.
    _write_session(tmp_path, UUID(int=1))

    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 1
    assert "inválida" in result.output.lower()


# ----------------------------------------------------------------------
# open
# ----------------------------------------------------------------------


def test_open_reports_no_session_found() -> None:
    result = runner.invoke(app, ["open"])

    assert result.exit_code == 1
    assert "Nenhuma sessão encontrada" in result.output


def test_open_calls_the_folder_opener_with_the_export_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = UUID(int=1)
    session_dir = _write_session(tmp_path, session_id)
    calls: list[Path] = []
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(os, "startfile", lambda path: calls.append(Path(path)), raising=False)

    result = runner.invoke(app, ["open"])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0].resolve() == session_dir.resolve()


# ----------------------------------------------------------------------
# logs
# ----------------------------------------------------------------------


def test_logs_reports_no_session_found() -> None:
    result = runner.invoke(app, ["logs"])

    assert result.exit_code == 1
    assert "Nenhuma sessão encontrada" in result.output


def test_logs_reports_no_records_when_none_match(tmp_path: Path) -> None:
    _write_session(tmp_path, UUID(int=1))

    result = runner.invoke(app, ["logs"])

    assert result.exit_code == 0
    assert "Nenhum registro de log encontrado" in result.output


def test_logs_shows_matching_records(tmp_path: Path) -> None:
    session_id = UUID(int=1)
    _write_session(tmp_path, session_id)
    log_engine = LoguruLogEngine(log_directory=tmp_path / "logs")
    log_engine.info("Sessão gravada com sucesso.", session_id=str(session_id))
    log_engine.flush()

    result = runner.invoke(app, ["logs"])

    assert result.exit_code == 0
    assert "Sessão gravada com sucesso." in result.output
