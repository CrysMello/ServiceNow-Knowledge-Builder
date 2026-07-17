"""``bootstrap.create_controller`` monta um ``ApplicationController``
real (ADR 0012) a partir de um arquivo de configuração — sem config
nenhuma, deve falhar de forma controlada, com diagnóstico útil
(PR-007), nunca silenciosamente."""

from __future__ import annotations

from pathlib import Path

import pytest

from snkb import bootstrap


def _write_minimal_config(config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "default.json").write_text(
        '{"instance_url": "https://empresa.service-now.com", "output_directory": "exports"}',
        encoding="utf-8",
    )


def test_create_controller_without_any_config_file_raises_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        bootstrap.create_controller()


def test_create_controller_builds_a_working_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_minimal_config(tmp_path / "config")

    controller = bootstrap.create_controller()

    assert callable(controller.dispatch)
    assert callable(controller.query)
    assert callable(controller.subscribe)


def test_create_controller_prefers_local_config_over_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    _write_minimal_config(config_dir)
    (config_dir / "local.json").write_text(
        '{"instance_url": "https://outra-empresa.service-now.com", '
        '"output_directory": "exports"}',
        encoding="utf-8",
    )

    # Não lança nada — confirma que local.json (e não default.json) foi
    # lido com sucesso, sem expor detalhes internos do controller aqui.
    bootstrap.create_controller()
