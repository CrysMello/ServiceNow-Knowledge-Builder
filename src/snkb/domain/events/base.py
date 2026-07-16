"""Base type shared by every domain event."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """Common envelope fields for all domain events.

    Concrete events extend this class and add only the data required by
    their subscribers (NAM-006: event names use the past tense).
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
