"""Selector entity: the ordered set of candidates for one element
(SRS section 10.5, Module Specifications Chapter 7)."""

from __future__ import annotations

from dataclasses import dataclass, field

from snkb.domain.value_objects.identifiers import ElementId
from snkb.domain.value_objects.selector_candidate import SelectorCandidate


@dataclass(slots=True)
class ElementSelectors:
    """All localisation strategies known for a given element, ordered by
    descending confidence score."""

    element_id: ElementId
    candidates: list[SelectorCandidate] = field(default_factory=list)

    @property
    def best_candidate(self) -> SelectorCandidate | None:
        """Highest-confidence candidate, or ``None`` if none exist."""
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda candidate: candidate.confidence_score)
