"""Exceptions raised by the Configuration Manager (CFG-006)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class ConfigurationError(KnowledgeBuilderError):
    """Base error for configuration loading and validation failures."""


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values fail validation before recording
    can start (RNF-023: invalid configuration must be rejected with a
    per-field message)."""
