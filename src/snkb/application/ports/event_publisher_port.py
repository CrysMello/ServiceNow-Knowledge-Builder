"""Port for publishing domain events (AI Coding Standards, section 12)."""

from __future__ import annotations

from typing import Protocol

from snkb.domain.events.base import DomainEvent


class EventPublisherPort(Protocol):
    """Publishes domain events to whichever subscribers are registered.

    Implementations must guarantee that an exception raised by one
    subscriber does not prevent other subscribers from receiving the
    event (AI Coding Standards, section 12: "Erros em um subscriber não
    deverão corromper o publisher").
    """

    def publish(self, event: DomainEvent) -> None: ...
