"""Events published by the Navigation Recorder (Module Specifications 5.14)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class PageOpened(DomainEvent):
    session_id: UUID
    page_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class PageClosed(DomainEvent):
    session_id: UUID
    page_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class PageUpdated(DomainEvent):
    session_id: UUID
    page_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class PageCaptured(DomainEvent):
    session_id: UUID
    page_id: UUID
    normalized_url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NavigationStarted(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class NavigationFinished(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class NavigationUrlChanged(DomainEvent):
    session_id: UUID
    url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RedirectDetected(DomainEvent):
    session_id: UUID
    from_url: str
    to_url: str
