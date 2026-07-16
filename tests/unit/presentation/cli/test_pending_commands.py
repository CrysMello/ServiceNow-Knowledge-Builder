"""Confirma que os comandos ainda dependentes de módulos não
implementados falham de forma limpa (exit code 1, mensagem clara),
nunca com um traceback bruto do Python."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from snkb.presentation.cli.main import app

runner = CliRunner()


@pytest.mark.parametrize(
    ("command_name", "expected_module"),
    [
        ("status", "Session Manager"),
        ("validate", "Export Engine"),
        ("open", "Export Engine"),
        ("logs", "Log Engine"),
        ("config", "Configuration Manager"),
    ],
)
def test_pending_command_fails_cleanly(command_name: str, expected_module: str) -> None:
    result = runner.invoke(app, [command_name])

    assert result.exit_code == 1
    assert expected_module in result.output
    assert "Traceback (most recent call last)" not in result.output
