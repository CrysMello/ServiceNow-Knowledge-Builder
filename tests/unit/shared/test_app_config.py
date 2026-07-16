"""Validates the ``AppConfig`` schema and its secure defaults (CFG-002)."""

from __future__ import annotations

from pathlib import Path

import pytest

from snkb.shared.dtos.app_config import AppConfig


def test_app_config_defaults_are_the_safest_option(tmp_path: Path) -> None:
    config = AppConfig(instance_url="https://empresa.service-now.com", output_directory=tmp_path)

    assert config.capture_policy.capture_field_values is False
    assert config.capture_policy.mask_sensitive_fields is True
    assert config.capture_policy.capture_authenticated_user is False


def test_app_config_rejects_blank_instance_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        AppConfig(instance_url="   ", output_directory=tmp_path)


def test_app_config_rejects_non_positive_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        AppConfig(
            instance_url="https://empresa.service-now.com",
            output_directory=tmp_path,
            browser_timeout_seconds=0,
        )
