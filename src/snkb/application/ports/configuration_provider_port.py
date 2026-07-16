"""Port for the Configuration Manager (CFG-001 through CFG-006)."""

from __future__ import annotations

from typing import Protocol

from snkb.shared.dtos.app_config import AppConfig


class ConfigurationProviderPort(Protocol):
    """Loads and validates the application configuration.

    Implementations must reject invalid configuration before recording
    can start, with a message identifying the offending field (CFG-006).
    """

    def load(self) -> AppConfig: ...
    def reload(self) -> AppConfig: ...
