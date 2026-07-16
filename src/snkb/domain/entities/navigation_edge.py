"""Navigation edge entity: a source-to-target page transition
(SRS section 10.3, RF-025, RF-026)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from snkb.domain.enums.navigation_type import NavigationType
from snkb.domain.enums.relation_type import RelationType
from snkb.domain.value_objects.identifiers import EventId, PageId


@dataclass(slots=True)
class NavigationEdge:
    """One directed transition in the navigation graph, linking the page a
    user was on to the page they reached and the event that caused it."""

    source_page_id: PageId
    target_page_id: PageId
    event_id: EventId
    navigation_type: NavigationType
    relation_type: RelationType
    confidence: int
    timestamp: datetime
    evidence: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100.")
