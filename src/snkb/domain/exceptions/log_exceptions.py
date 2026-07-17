"""Exceptions raised by the Log Engine (Module Specifications, Chapter 10)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class InvalidLogLevelError(KnowledgeBuilderError):
    """Raised when a configured or requested log level does not match any
    value of ``domain.enums.log_level.LogLevel``."""
