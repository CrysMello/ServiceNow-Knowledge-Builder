"""Events published by the Selector Analyzer (Module Specifications 7.15)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectorsReady(DomainEvent):
    session_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectorUpdated(DomainEvent):
    session_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectorConflict(DomainEvent):
    session_id: UUID
    element_id: UUID
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectorRemoved(DomainEvent):
    session_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class LowConfidenceSelector(DomainEvent):
    session_id: UUID
    element_id: UUID
    confidence_score: int
