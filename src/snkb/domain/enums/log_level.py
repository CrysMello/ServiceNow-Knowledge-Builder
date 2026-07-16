"""Log severity levels (Module Specifications Chapter 10, section 10.7)."""

from __future__ import annotations

from enum import StrEnum


class LogLevel(StrEnum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
