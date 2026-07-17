"""Testes de integração leve da CLI usando ``typer.testing.CliRunner``
(sem terminal real, sem Playwright, sem display).

Usa ``result.output`` (não ``result.stdout``) porque é o atributo
estável do ``click.testing.CliRunner`` que captura tudo o que foi
impresso, independentemente de a mensagem ter ido para stdout ou
stderr.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from snkb import __version__
from snkb.presentation.cli.main import app

runner = CliRunner()


def test_help_lists_all_seven_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command_name in (
        "record",
        "status",
        "validate",
        "open",
        "logs",
        "config",
        "version",
    ):
        assert command_name in result.output


def test_version_command_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_record_without_instance_url_fails_with_usage_error() -> None:
    result = runner.invoke(app, ["record"])

    assert result.exit_code != 0


def test_record_fails_cleanly_without_a_configuration_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem ``config/default.json``/``config/local.json`` (Configuration
    Manager ainda não implementado — ver ADR 0012), ``bootstrap.
    create_controller`` levanta ``FileNotFoundError``; o comando deve
    reportar isso de forma limpa, nunca com um traceback bruto."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["record", "--instance-url", "https://empresa.service-now.com"])

    assert result.exit_code == 1
    assert "config" in result.output.lower()
    assert "Traceback (most recent call last)" not in result.output
