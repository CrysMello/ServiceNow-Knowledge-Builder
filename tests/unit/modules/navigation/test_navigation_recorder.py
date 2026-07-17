"""Testes do ``NavigationRecorder`` — puros, sem I/O (Module
Specifications, Capítulo 5)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest

from snkb.domain.entities.page import Page
from snkb.domain.enums.relation_type import RelationType
from snkb.domain.events.navigation_events import (
    NavigationFinished,
    NavigationStarted,
    PageCaptured,
    PageClosed,
    PageOpened,
    PageUpdated,
    RedirectDetected,
)
from snkb.domain.exceptions.navigation_exceptions import (
    InvalidNavigationUrlError,
    NavigationAlreadyActiveError,
    NavigationNotActiveError,
    NoPendingNavigationError,
    PageNotFoundError,
    RedirectLoopError,
)
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.shared.dtos.navigation_json import NavigationJsonModel

_SESSION_ID = UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")
_INSTANCE = "https://empresa.service-now.com"


class _RecordingEventPublisher:
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)

    def of_type(self, event_type: type) -> list[object]:
        return [event for event in self.published if isinstance(event, event_type)]


class _RecordingLogEngine:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def trace(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def debug(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def info(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def warning(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def error(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def critical(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def exception(self, message: str, **context: object) -> None:
        self.messages.append(message)

    def flush(self) -> None:
        """Nenhuma escrita real ocorre neste duplo de teste."""

    def export(self) -> list[dict[str, object]]:
        return []

    def statistics(self) -> dict[str, object]:
        return {}


def _sequential_uuid_factory() -> Callable[[], UUID]:
    counter = itertools.count(1)
    return lambda: UUID(int=next(counter))


def _make_recorder(
    now: Callable[[], datetime] | None = None,
    generate_id: Callable[[], UUID] | None = None,
    max_redirect_chain: int = 10,
) -> tuple[NavigationRecorder, _RecordingEventPublisher, _RecordingLogEngine]:
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()
    recorder = NavigationRecorder(
        event_publisher=publisher,
        log_engine=log,
        now=now or (lambda: datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC)),
        generate_id=generate_id or _sequential_uuid_factory(),
        max_redirect_chain=max_redirect_chain,
    )
    return recorder, publisher, log


# ----------------------------------------------------------------------
# start / stop
# ----------------------------------------------------------------------


def test_start_publishes_navigation_started() -> None:
    recorder, publisher, _log = _make_recorder()

    recorder.start(_SESSION_ID)

    assert publisher.of_type(NavigationStarted) != []


def test_start_twice_is_rejected() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)

    with pytest.raises(NavigationAlreadyActiveError):
        recorder.start(_SESSION_ID)


def test_stop_publishes_navigation_finished() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)

    recorder.stop()

    assert publisher.of_type(NavigationFinished) != []


def test_operations_before_start_are_rejected() -> None:
    recorder, _publisher, _log = _make_recorder()

    with pytest.raises(NavigationNotActiveError):
        recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home")
    with pytest.raises(NavigationNotActiveError):
        recorder.capture_page()
    with pytest.raises(NavigationNotActiveError):
        recorder.export_navigation()


# ----------------------------------------------------------------------
# capture_page
# ----------------------------------------------------------------------


def test_capture_page_without_observation_is_rejected() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)

    with pytest.raises(NoPendingNavigationError):
        recorder.capture_page()


def test_capture_page_builds_a_page_and_publishes_events() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home", title="Home")

    page = recorder.capture_page()

    assert isinstance(page, Page)
    assert page.title == "Home"
    assert page.url.value == f"{_INSTANCE}/home"
    assert recorder.get_current_page() is page
    assert recorder.get_page_history() == [page]
    assert publisher.of_type(PageCaptured) != []
    assert publisher.of_type(PageOpened) != []


def test_capturing_the_same_url_twice_does_not_duplicate_the_page() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home", title="Home")
    first = recorder.capture_page()

    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/list", title="Lista")
    recorder.capture_page()
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home", title="Home")
    second = recorder.capture_page()

    assert first.page_id == second.page_id
    assert len(recorder.get_page_history()) == 2
    assert len(publisher.of_type(PageOpened)) == 2


def test_capture_page_with_invalid_url_raises() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url="not-a-valid-url")

    with pytest.raises(InvalidNavigationUrlError):
        recorder.capture_page()


def test_navigating_between_two_pages_creates_an_observed_edge() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home", title="Home")
    home = recorder.capture_page()
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/list", title="Lista")
    listing = recorder.capture_page()

    edges = recorder.get_navigation_graph()

    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_page_id == home.page_id
    assert edge.target_page_id == listing.page_id
    assert edge.relation_type == RelationType.OBSERVED
    assert edge.confidence == 100


# ----------------------------------------------------------------------
# Redirecionamentos
# ----------------------------------------------------------------------


def test_consecutive_observations_without_capture_publish_redirect_detected() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/a")

    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/b")

    redirects = publisher.of_type(RedirectDetected)
    assert len(redirects) == 1
    assert redirects[0].from_url == f"{_INSTANCE}/a"
    assert redirects[0].to_url == f"{_INSTANCE}/b"


def test_redirect_chain_beyond_the_limit_raises() -> None:
    recorder, _publisher, _log = _make_recorder(max_redirect_chain=2)
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/a")
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/b")

    with pytest.raises(RedirectLoopError):
        recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/c")


def test_capturing_resets_the_redirect_chain() -> None:
    recorder, _publisher, _log = _make_recorder(max_redirect_chain=2)
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/a")
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/b")
    recorder.capture_page()

    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/c")
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/d")

    # Não levanta RedirectLoopError porque o capture_page() intermediário
    # reiniciou a contagem da cadeia.


# ----------------------------------------------------------------------
# update_page / close_page
# ----------------------------------------------------------------------


def test_update_page_applies_a_later_observed_title() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home")
    page = recorder.capture_page()
    assert page.title == f"{_INSTANCE}/home"

    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home", title="Home real")
    updated = recorder.update_page(page.page_id.value)

    assert updated.title == "Home real"
    assert updated.revision_id == 2
    assert publisher.of_type(PageUpdated) != []


def test_update_page_with_unknown_id_raises() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)

    with pytest.raises(PageNotFoundError):
        recorder.update_page(UUID("00000000-0000-0000-0000-000000000000"))


def test_close_page_clears_current_page_and_publishes_event() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home")
    page = recorder.capture_page()

    recorder.close_page(page.page_id.value)

    assert recorder.get_current_page() is None
    assert publisher.of_type(PageClosed) != []


def test_close_page_with_unknown_id_raises() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)

    with pytest.raises(PageNotFoundError):
        recorder.close_page(UUID("00000000-0000-0000-0000-000000000000"))


# ----------------------------------------------------------------------
# export_navigation / clear_navigation
# ----------------------------------------------------------------------


def test_export_navigation_matches_the_navigation_json_schema() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home", title="Home")
    recorder.capture_page()
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/list", title="Lista")
    recorder.capture_page()

    exported = recorder.export_navigation()
    model = NavigationJsonModel(**exported)

    assert model.session_id == _SESSION_ID
    assert len(model.nodes) == 2
    assert len(model.edges) == 1
    assert len(model.timeline) == 2


def test_clear_navigation_resets_all_state() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home")
    recorder.capture_page()

    recorder.clear_navigation()

    assert recorder.get_current_page() is None
    assert recorder.get_page_history() == []
    assert recorder.get_navigation_graph() == []
    with pytest.raises(NavigationNotActiveError):
        recorder.capture_page()

    recorder.start(_SESSION_ID)
    recorder.observe_navigation(tab_id="tab-1", url=f"{_INSTANCE}/home")
    recorder.capture_page()
    assert len(recorder.get_page_history()) == 1
