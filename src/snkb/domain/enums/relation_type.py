"""Confidence classification of a navigation-graph edge (RF-025, RF-026)."""

from __future__ import annotations

from enum import StrEnum


class RelationType(StrEnum):
    """Whether a page-to-page dependency was witnessed, inferred or entered
    manually during session review (RF-026: never present inference as
    observed fact without marking it)."""

    OBSERVED = "observed"
    INFERRED = "inferred"
    MANUAL = "manual"
