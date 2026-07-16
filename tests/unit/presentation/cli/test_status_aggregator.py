"""Testes do agregador de contadores de gravação."""

from __future__ import annotations

from uuid import UUID

from snkb.domain.events.export_events import ExportFailed
from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.session_events import SessionFailed, SessionStarted
from snkb.domain.events.system_events import ErrorOccurred
from snkb.presentation.cli.status_aggregator import RecordingCounterAggregator
from snkb.presentation.cli.view_models import RecordingCounters


def test_page_captured_increments_page_count(
    fixed_session_uuid: UUID, fixed_page_uuid: UUID
) -> None:
    counters = RecordingCounters()
    aggregator = RecordingCounterAggregator()

    aggregator.apply(
        counters,
        PageCaptured(
            session_id=fixed_session_uuid,
            page_id=fixed_page_uuid,
            normalized_url="https://empresa.service-now.com/home",
        ),
    )
    aggregator.apply(
        counters,
        PageCaptured(
            session_id=fixed_session_uuid,
            page_id=fixed_page_uuid,
            normalized_url="https://empresa.service-now.com/list",
        ),
    )

    assert counters.page_count == 2
    assert counters.error_count == 0


def test_failure_events_increment_error_count(fixed_session_uuid: UUID) -> None:
    counters = RecordingCounters()
    aggregator = RecordingCounterAggregator()

    aggregator.apply(counters, ExportFailed(session_id=fixed_session_uuid, reason="x"))
    aggregator.apply(counters, SessionFailed(session_id=fixed_session_uuid, reason="y"))
    aggregator.apply(
        counters, ErrorOccurred(session_id=fixed_session_uuid, module="m", message="z")
    )

    assert counters.error_count == 3
    assert counters.page_count == 0


def test_unrelated_event_does_not_change_counters(fixed_session_uuid: UUID) -> None:
    counters = RecordingCounters()
    aggregator = RecordingCounterAggregator()

    aggregator.apply(counters, SessionStarted(session_id=fixed_session_uuid))

    assert counters.page_count == 0
    assert counters.error_count == 0
