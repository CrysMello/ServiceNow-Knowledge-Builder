"""Testes do agregador de contadores do Painel de Status."""

from __future__ import annotations

from uuid import UUID

from snkb.domain.events.export_events import ExportFailed
from snkb.domain.events.navigation_events import PageCaptured
from snkb.domain.events.session_events import SessionFailed
from snkb.domain.events.system_events import ErrorOccurred
from snkb.presentation.status_aggregator import StatusAggregator
from snkb.presentation.view_models import StatusPanelViewModel


def test_page_captured_increments_page_count(
    fixed_session_uuid: UUID, fixed_page_uuid: UUID
) -> None:
    view_model = StatusPanelViewModel()
    aggregator = StatusAggregator()

    aggregator.apply(
        view_model,
        PageCaptured(
            session_id=fixed_session_uuid,
            page_id=fixed_page_uuid,
            normalized_url="https://empresa.service-now.com/home",
        ),
    )
    aggregator.apply(
        view_model,
        PageCaptured(
            session_id=fixed_session_uuid,
            page_id=fixed_page_uuid,
            normalized_url="https://empresa.service-now.com/list",
        ),
    )

    assert view_model.page_count == 2
    assert view_model.error_count == 0


def test_failure_events_increment_error_count(fixed_session_uuid: UUID) -> None:
    view_model = StatusPanelViewModel()
    aggregator = StatusAggregator()

    aggregator.apply(view_model, ExportFailed(session_id=fixed_session_uuid, reason="x"))
    aggregator.apply(view_model, SessionFailed(session_id=fixed_session_uuid, reason="y"))
    aggregator.apply(
        view_model,
        ErrorOccurred(session_id=fixed_session_uuid, module="m", message="z"),
    )

    assert view_model.error_count == 3
    assert view_model.page_count == 0


def test_unrelated_event_does_not_change_counters(fixed_session_uuid: UUID) -> None:
    from snkb.domain.events.session_events import SessionStarted

    view_model = StatusPanelViewModel()
    aggregator = StatusAggregator()

    aggregator.apply(view_model, SessionStarted(session_id=fixed_session_uuid))

    assert view_model.page_count == 0
    assert view_model.error_count == 0
