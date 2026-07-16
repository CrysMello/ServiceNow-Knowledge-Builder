"""Unit tests for domain events."""

from __future__ import annotations

from uuid import UUID

import pytest

from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.session_events import SessionStarted


def test_domain_event_generates_id_and_timestamp_by_default(fixed_session_uuid: UUID) -> None:
    event = SessionStarted(session_id=fixed_session_uuid)

    assert event.session_id == fixed_session_uuid
    assert event.event_id is not None
    assert event.occurred_at is not None


def test_domain_events_are_immutable(fixed_session_uuid: UUID, fixed_page_uuid: UUID) -> None:
    event = PageCaptured(
        session_id=fixed_session_uuid,
        page_id=fixed_page_uuid,
        normalized_url="https://empresa.service-now.com/home",
    )

    with pytest.raises(AttributeError):
        event.normalized_url = "https://tampered"  # type: ignore[misc]
