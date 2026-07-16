"""Events published by the Screenshot Engine (Module Specifications 8.15)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class ScreenshotCreated(DomainEvent):
    session_id: UUID
    page_id: UUID
    screenshot_id: UUID
    file_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ScreenshotUpdated(DomainEvent):
    session_id: UUID
    screenshot_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ScreenshotFailed(DomainEvent):
    session_id: UUID
    page_id: UUID
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ScreenshotSkipped(DomainEvent):
    session_id: UUID
    page_id: UUID
    reason: str
