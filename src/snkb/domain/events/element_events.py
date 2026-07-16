"""Events published by the Element Recorder (Module Specifications 6.15)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class ElementFound(DomainEvent):
    session_id: UUID
    page_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ElementUpdated(DomainEvent):
    session_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ElementRemoved(DomainEvent):
    session_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ElementsCaptured(DomainEvent):
    session_id: UUID
    page_id: UUID
    element_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class FormDetected(DomainEvent):
    session_id: UUID
    page_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class GridDetected(DomainEvent):
    session_id: UUID
    page_id: UUID
    element_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RelatedListDetected(DomainEvent):
    session_id: UUID
    page_id: UUID
    element_id: UUID
