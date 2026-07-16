"""Unit tests for domain value objects."""

from __future__ import annotations

from uuid import UUID

import pytest

from snkb.domain.enums.selector_strategy_type import SelectorStrategyType
from snkb.domain.value_objects.identifiers import PageId, SessionId
from snkb.domain.value_objects.selector_candidate import SelectorCandidate
from snkb.domain.value_objects.url import NormalizedUrl
from snkb.domain.value_objects.viewport import Resolution, Viewport


def test_session_id_equality_is_value_based(fixed_session_uuid: UUID) -> None:
    first = SessionId(fixed_session_uuid)
    second = SessionId(fixed_session_uuid)

    assert first == second
    assert str(first) == str(fixed_session_uuid)


def test_session_id_and_page_id_are_distinct_types(fixed_session_uuid: UUID) -> None:
    session_id = SessionId(fixed_session_uuid)
    page_id = PageId(fixed_session_uuid)

    assert session_id != page_id


def test_normalized_url_rejects_empty_value() -> None:
    with pytest.raises(ValueError):
        NormalizedUrl("")


def test_resolution_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        Resolution(width=0, height=1080)


def test_viewport_accepts_positive_dimensions() -> None:
    viewport = Viewport(width=1920, height=1080)

    assert viewport.width == 1920
    assert viewport.height == 1080


def test_selector_candidate_rejects_out_of_range_score() -> None:
    with pytest.raises(ValueError):
        SelectorCandidate(
            strategy=SelectorStrategyType.ID,
            value="#save",
            confidence_score=150,
            stability_score=50,
        )
