"""Testes do ``JsonConfigurationProvider`` (Configuration Manager,
CFG-001 a CFG-006, ADR 0015)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from snkb.domain.exceptions.configuration_exceptions import (
    ConfigurationError,
    InvalidConfigurationError,
)
from snkb.infrastructure.configuration.configuration_manager import JsonConfigurationProvider

_VALID_CONFIG: dict[str, object] = {
    "instance_url": "https://empresa.service-now.com",
    "output_directory": "exports",
}


def _write_config(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_returns_valid_app_config(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path / "local.json", _VALID_CONFIG)
    provider = JsonConfigurationProvider(candidates=(config_file,))

    config = provider.load()

    assert config.instance_url == "https://empresa.service-now.com"


def test_load_prefers_the_first_existing_candidate(tmp_path: Path) -> None:
    first = _write_config(
        tmp_path / "local.json", {**_VALID_CONFIG, "instance_url": "https://primeira.example"}
    )
    second = _write_config(
        tmp_path / "default.json", {**_VALID_CONFIG, "instance_url": "https://segunda.example"}
    )
    provider = JsonConfigurationProvider(candidates=(first, second))

    config = provider.load()

    assert config.instance_url == "https://primeira.example"


def test_load_falls_back_to_the_next_candidate_when_first_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "local.json"
    existing = _write_config(tmp_path / "default.json", _VALID_CONFIG)
    provider = JsonConfigurationProvider(candidates=(missing, existing))

    config = provider.load()

    assert config.instance_url == _VALID_CONFIG["instance_url"]


def test_load_raises_configuration_error_when_no_candidate_exists(tmp_path: Path) -> None:
    provider = JsonConfigurationProvider(candidates=(tmp_path / "nope.json",))

    with pytest.raises(ConfigurationError):
        provider.load()


def test_load_raises_invalid_configuration_error_naming_the_offending_field(
    tmp_path: Path,
) -> None:
    config_file = _write_config(tmp_path / "local.json", {**_VALID_CONFIG, "resolution_width": -10})
    provider = JsonConfigurationProvider(candidates=(config_file,))

    with pytest.raises(InvalidConfigurationError) as excinfo:
        provider.load()

    assert "resolution_width" in str(excinfo.value)


def test_load_raises_invalid_configuration_error_for_blank_instance_url(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path / "local.json", {**_VALID_CONFIG, "instance_url": "  "})
    provider = JsonConfigurationProvider(candidates=(config_file,))

    with pytest.raises(InvalidConfigurationError) as excinfo:
        provider.load()

    assert "instance_url" in str(excinfo.value)


def test_reload_rereads_the_file_from_disk(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path / "local.json", _VALID_CONFIG)
    provider = JsonConfigurationProvider(candidates=(config_file,))
    provider.load()

    _write_config(config_file, {**_VALID_CONFIG, "instance_url": "https://atualizada.example"})
    reloaded = provider.reload()

    assert reloaded.instance_url == "https://atualizada.example"
