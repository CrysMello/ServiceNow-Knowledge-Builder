"""Testes de ``snkb config`` via ``typer.testing.CliRunner`` (ADR
0015: Configuration Manager)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from snkb.presentation.cli.main import app

runner = CliRunner()


def test_config_prints_the_effective_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.json").write_text(
        json.dumps(
            {"instance_url": "https://empresa.service-now.com", "output_directory": "exports"}
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0
    assert "https://empresa.service-now.com" in result.output
    assert "capture_policy:" in result.output
    assert "login_detection:" in result.output


def test_config_fails_cleanly_without_a_configuration_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 1
    assert "config" in result.output.lower()
    assert "Traceback (most recent call last)" not in result.output


def test_config_reports_the_invalid_field_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.json").write_text(
        json.dumps(
            {
                "instance_url": "https://empresa.service-now.com",
                "output_directory": "exports",
                "resolution_width": -1,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 1
    assert "resolution_width" in result.output
