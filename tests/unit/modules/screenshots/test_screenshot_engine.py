"""Testes do ``ScreenshotEngine`` — puros, sem I/O (Module
Specifications, Capítulo 8)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest

from snkb.domain.entities.screenshot import Screenshot
from snkb.domain.enums.screenshot_type import ScreenshotType
from snkb.domain.events.screenshot_events import (
    ScreenshotCreated,
    ScreenshotFailed,
    ScreenshotSkipped,
)
from snkb.domain.exceptions.screenshot_exceptions import (
    NoPendingCaptureError,
    ScreenshotCaptureError,
    ScreenshotNotFoundError,
)
from snkb.modules.screenshots.screenshot_engine import RawScreenshotObservation, ScreenshotEngine
from snkb.shared.dtos.app_config import CapturePolicyModel

_SESSION_ID = UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")
_PAGE_ID = UUID("1c2d3e4f-5a6b-47c8-89d0-1234567890ab")
_OTHER_PAGE_ID = UUID("2c2d3e4f-5a6b-47c8-89d0-1234567890ab")


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


def _make_engine(
    capture_policy: CapturePolicyModel | None = None,
    generate_id: Callable[[], UUID] | None = None,
    now: Callable[[], datetime] | None = None,
) -> tuple[ScreenshotEngine, _RecordingEventPublisher, _RecordingLogEngine]:
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()
    engine = ScreenshotEngine(
        event_publisher=publisher,
        log_engine=log,
        capture_policy=capture_policy or CapturePolicyModel(),
        now=now or (lambda: datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC)),
        generate_id=generate_id or _sequential_uuid_factory(),
    )
    return engine, publisher, log


# ----------------------------------------------------------------------
# Pré-condições
# ----------------------------------------------------------------------


def test_capture_without_staging_raises() -> None:
    engine, _publisher, _log = _make_engine()

    with pytest.raises(NoPendingCaptureError):
        engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)


def test_capture_with_policy_disabled_raises_and_publishes_skipped() -> None:
    engine, publisher, _log = _make_engine(
        capture_policy=CapturePolicyModel(capture_screenshots=False)
    )
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=100, height=100),
    )

    with pytest.raises(NoPendingCaptureError):
        engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)

    assert len(publisher.of_type(ScreenshotSkipped)) == 1


# ----------------------------------------------------------------------
# capture()
# ----------------------------------------------------------------------


def test_capture_builds_screenshot_and_publishes_created() -> None:
    engine, publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=1920, height=1080),
    )

    screenshot = engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)

    assert isinstance(screenshot, Screenshot)
    assert screenshot.width == 1920
    assert screenshot.height == 1080
    assert screenshot.capture_type == ScreenshotType.VIEWPORT
    assert screenshot.file_name == f"{_PAGE_ID}_viewport_001.png"
    assert len(publisher.of_type(ScreenshotCreated)) == 1


def test_capture_with_invalid_dimensions_raises_and_publishes_failed() -> None:
    engine, publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=0, height=100),
    )

    with pytest.raises(ScreenshotCaptureError):
        engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)

    assert len(publisher.of_type(ScreenshotFailed)) == 1


def test_sequence_increments_per_page_across_captures() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600),
    )
    first = engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)
    engine.stage_capture(
        _SESSION_ID, _PAGE_ID, ScreenshotType.MODAL, RawScreenshotObservation(width=400, height=300)
    )
    second = engine.capture(_PAGE_ID, ScreenshotType.MODAL)

    assert first.file_name == f"{_PAGE_ID}_viewport_001.png"
    assert second.file_name == f"{_PAGE_ID}_modal_002.png"


# ----------------------------------------------------------------------
# capture_page / capture_modal / capture_popup
# ----------------------------------------------------------------------


def test_capture_page_uses_viewport_by_default() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600),
    )

    screenshot = engine.capture_page(_PAGE_ID)

    assert screenshot.capture_type == ScreenshotType.VIEWPORT


def test_capture_page_uses_full_page_when_policy_enables_it() -> None:
    engine, _publisher, _log = _make_engine(
        capture_policy=CapturePolicyModel(full_page_screenshots=True)
    )
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.FULL_PAGE,
        RawScreenshotObservation(width=800, height=3000),
    )

    screenshot = engine.capture_page(_PAGE_ID)

    assert screenshot.capture_type == ScreenshotType.FULL_PAGE


def test_capture_modal_and_popup_use_matching_types() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID, _PAGE_ID, ScreenshotType.MODAL, RawScreenshotObservation(width=400, height=300)
    )
    engine.stage_capture(
        _SESSION_ID, _PAGE_ID, ScreenshotType.POPUP, RawScreenshotObservation(width=300, height=200)
    )

    modal = engine.capture_modal(_PAGE_ID)
    popup = engine.capture_popup(_PAGE_ID)

    assert modal.capture_type == ScreenshotType.MODAL
    assert popup.capture_type == ScreenshotType.POPUP


# ----------------------------------------------------------------------
# validate / get_screenshot
# ----------------------------------------------------------------------


def test_validate_returns_true_for_a_well_formed_screenshot() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600, byte_size=1024),
    )
    screenshot = engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)

    assert engine.validate(screenshot.screenshot_id.value) is True


def test_validate_returns_false_for_empty_byte_size() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600, byte_size=0),
    )
    screenshot = engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)

    assert engine.validate(screenshot.screenshot_id.value) is False


def test_validate_returns_false_for_unknown_id() -> None:
    engine, _publisher, _log = _make_engine()

    assert engine.validate(UUID(int=999)) is False


def test_get_screenshot_returns_none_for_unknown_id() -> None:
    engine, _publisher, _log = _make_engine()

    assert engine.get_screenshot(UUID(int=999)) is None


# ----------------------------------------------------------------------
# delete / clear
# ----------------------------------------------------------------------


def test_delete_removes_screenshot() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600),
    )
    screenshot = engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)

    engine.delete(screenshot.screenshot_id.value)

    assert engine.get_screenshot(screenshot.screenshot_id.value) is None


def test_delete_unknown_id_raises() -> None:
    engine, _publisher, _log = _make_engine()

    with pytest.raises(ScreenshotNotFoundError):
        engine.delete(UUID(int=999))


def test_clear_only_affects_the_given_page() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600),
    )
    kept = engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)
    engine.stage_capture(
        _SESSION_ID,
        _OTHER_PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600),
    )
    other = engine.capture(_OTHER_PAGE_ID, ScreenshotType.VIEWPORT)

    engine.clear(_PAGE_ID)

    assert engine.get_screenshot(kept.screenshot_id.value) is None
    assert engine.get_screenshot(other.screenshot_id.value) is other


def test_clear_drops_staged_but_uncaptured_observations() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600),
    )

    engine.clear(_PAGE_ID)

    with pytest.raises(NoPendingCaptureError):
        engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)


# ----------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------


def test_statistics_aggregates_by_capture_type() -> None:
    engine, _publisher, _log = _make_engine()
    engine.stage_capture(
        _SESSION_ID,
        _PAGE_ID,
        ScreenshotType.VIEWPORT,
        RawScreenshotObservation(width=800, height=600),
    )
    engine.capture(_PAGE_ID, ScreenshotType.VIEWPORT)
    engine.stage_capture(
        _SESSION_ID, _PAGE_ID, ScreenshotType.MODAL, RawScreenshotObservation(width=400, height=300)
    )
    engine.capture(_PAGE_ID, ScreenshotType.MODAL)

    stats = engine.statistics()

    assert stats["total_screenshots"] == 2
    assert stats["pages_with_screenshots"] == 1
    assert stats["by_capture_type"] == {"viewport": 1, "modal": 1}
