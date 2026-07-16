"""Events published by the Export Engine (Module Specifications 9.15)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snkb.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportStarted(DomainEvent):
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportProgress(DomainEvent):
    session_id: UUID
    step: str
    percentage: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportCompleted(DomainEvent):
    session_id: UUID
    output_directory: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportFailed(DomainEvent):
    session_id: UUID
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportCreated(DomainEvent):
    session_id: UUID
    report_path: str
