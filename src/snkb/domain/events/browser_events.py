"""Events published by the Browser Manager (Module Specifications 3.15)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class BrowserStarted(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class BrowserStopped(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginDetected(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class PageChanged(DomainEvent):
    session_id: UUID
    url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UrlChanged(DomainEvent):
    session_id: UUID
    url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TabCreated(DomainEvent):
    session_id: UUID
    tab_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TabClosed(DomainEvent):
    session_id: UUID
    tab_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BrowserTimeout(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class BrowserCrashed(DomainEvent):
    session_id: UUID
    reason: str
