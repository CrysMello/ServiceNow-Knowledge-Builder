"""Formata a configuração efetiva (``AppConfig``) em um bloco de texto
de terminal para ``snkb config``."""

from __future__ import annotations

from snkb.shared.dtos.app_config import AppConfig

_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "instance_url",
    "output_directory",
    "browser_timeout_seconds",
    "headless",
    "resolution_width",
    "resolution_height",
    "user_agent",
    "downloads_enabled",
    "language",
    "log_level",
    "log_retention_days",
    "max_journal_loss_seconds",
)


def format_config(config: AppConfig) -> str:
    """Bloco de texto multilinha com todos os campos da configuração
    efetiva, incluindo as políticas de captura e detecção de login."""
    lines = [f"{field}: {getattr(config, field)}" for field in _TOP_LEVEL_FIELDS]

    lines.append("capture_policy:")
    for field, value in config.capture_policy.model_dump().items():
        lines.append(f"  {field}: {value}")

    lines.append("login_detection:")
    for field, value in config.login_detection.model_dump().items():
        lines.append(f"  {field}: {value}")

    return "\n".join(lines)
