"""Unit tests for domain entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from snkb.domain.entities.navigation_edge import NavigationEdge
from snkb.domain.entities.page import Page
from snkb.domain.entities.session import Session
from snkb.domain.enums.navigation_type import NavigationType
from snkb.domain.enums.relation_type import RelationType
from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.value_objects.identifiers import EventId, PageId, SessionId
from snkb.domain.value_objects.url import NormalizedUrl


def test_session_duration_is_none_until_finished(
    fixed_session_uuid: UUID, fixed_now: datetime
) -> None:
    session = Session(
        session_id=SessionId(fixed_session_uuid),
        instance_url="https://empresa.service-now.com",
        created_at=fixed_now,
        status=SessionStatus.RECORDING,
        recording_start=fixed_now,
    )

    assert session.duration_seconds is None


def test_session_duration_is_computed_once_finished(
    fixed_session_uuid: UUID, fixed_now: datetime
) -> None:
    session = Session(
        session_id=SessionId(fixed_session_uuid),
        instance_url="https://empresa.service-now.com",
        created_at=fixed_now,
        status=SessionStatus.COMPLETED,
        recording_start=fixed_now,
        recording_end=fixed_now + timedelta(seconds=90),
    )

    assert session.duration_seconds == 90.0


def test_page_defaults_to_first_revision(
    fixed_page_uuid: UUID, fixed_session_uuid: UUID, fixed_now: datetime
) -> None:
    page = Page(
        page_id=PageId(fixed_page_uuid),
        session_id=SessionId(fixed_session_uuid),
        name_original="home",
        title="Home",
        url=NormalizedUrl("https://empresa.service-now.com/home"),
        fingerprint="abc123",
        first_seen=fixed_now,
    )

    assert page.revision_id == 1
    assert page.element_ids == []


def test_navigation_edge_rejects_invalid_confidence(fixed_page_uuid: UUID) -> None:
    other_page = PageId(UUID("00000000-0000-0000-0000-000000000002"))

    with pytest.raises(ValueError):
        NavigationEdge(
            source_page_id=PageId(fixed_page_uuid),
            target_page_id=other_page,
            event_id=EventId(UUID("00000000-0000-0000-0000-000000000003")),
            navigation_type=NavigationType.MANUAL,
            relation_type=RelationType.OBSERVED,
            confidence=150,
            timestamp=datetime.now(UTC),
        )
