"""Events published by the Session Manager (Module Specifications 4.11)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionCreated(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionStarted(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionPaused(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionResumed(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionFinished(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionFailed(DomainEvent):
    session_id: UUID
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionTimeout(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionExpired(DomainEvent):
    session_id: UUID
