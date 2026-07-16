"""Value object representing a single selector candidate for an element.

See Module Specifications, Chapter 7 (Selector Analyzer) and SRS section
10.5. A candidate is immutable evidence produced by the Selector Analyzer;
mutation means creating a new candidate, never patching an existing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from snkb.domain.enums.selector_strategy_type import SelectorStrategyType


@dataclass(frozen=True, slots=True)
class SelectorCandidate:
    """A single localisation strategy proposed for an element."""

    strategy: SelectorStrategyType
    value: str
    confidence_score: int
    stability_score: int
    uniqueness_count: int | None = None
    validated_at: datetime | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence_score <= 100:
            raise ValueError("confidence_score must be between 0 and 100.")
        if not 0 <= self.stability_score <= 100:
            raise ValueError("stability_score must be between 0 and 100.")
