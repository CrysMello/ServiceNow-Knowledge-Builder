"""Strongly typed identifiers used throughout the domain.

Wrapping ``uuid.UUID`` in dedicated value objects prevents accidentally
passing a session identifier where a page identifier is expected, and keeps
identity independent from any export file name (RF-029, RN-009).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionId:
    """Unique identifier of a recording session (RF-001, RN-004)."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class PageId:
    """Unique identifier of a logical page captured during a session."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class FrameId:
    """Unique identifier of a frame or iframe within a page (RF-009)."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ElementId:
    """Unique identifier of an interactive or structural element."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class SelectorId:
    """Unique identifier of a selector candidate for an element."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ScreenshotId:
    """Unique identifier of a captured screenshot (RF-023, RF-024)."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class EventId:
    """Unique identifier of a domain event instance."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)
