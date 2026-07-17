"""Testes do ``ElementRecorder`` — puros, sem I/O (Module
Specifications, Capítulo 6)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from uuid import UUID

import pytest

from snkb.domain.entities.element import Element
from snkb.domain.enums.element_semantic_type import ElementSemanticType
from snkb.domain.enums.sensitivity_classification import SensitivityClassification
from snkb.domain.events.element_events import (
    ElementFound,
    ElementRemoved,
    ElementsCaptured,
    ElementUpdated,
    FormDetected,
    GridDetected,
    RelatedListDetected,
)
from snkb.domain.exceptions.element_exceptions import ElementNotFoundError, NoPendingElementsError
from snkb.modules.elements.element_recorder import ElementRecorder, RawElementObservation

_SESSION_ID = UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")
_PAGE_ID = UUID("1c2d3e4f-5a6b-47c8-89d0-1234567890ab")
_OTHER_PAGE_ID = UUID("2c2d3e4f-5a6b-47c8-89d0-1234567890ab")
_FRAME_ORIGIN = "https://empresa.service-now.com"


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
    generate_id: Callable[[], UUID] | None = None,
) -> tuple[ElementRecorder, _RecordingEventPublisher, _RecordingLogEngine]:
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()
    recorder = ElementRecorder(
        event_publisher=publisher,
        log_engine=log,
        generate_id=generate_id or _sequential_uuid_factory(),
    )
    return recorder, publisher, log


def _text_input(**overrides: object) -> RawElementObservation:
    base: dict[str, object] = {
        "frame_origin": _FRAME_ORIGIN,
        "frame_selector": None,
        "tag": "input",
        "input_type": "text",
        "html_id": "short_description",
        "name": "short_description",
    }
    base.update(overrides)
    return RawElementObservation(**base)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# capture_elements
# ----------------------------------------------------------------------


def test_capture_elements_without_observation_raises() -> None:
    recorder, _publisher, _log = _make_recorder()

    with pytest.raises(NoPendingElementsError):
        recorder.capture_elements(_PAGE_ID)


def test_capture_elements_builds_and_publishes() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input()])

    elements = recorder.capture_elements(_PAGE_ID)

    assert len(elements) == 1
    element = elements[0]
    assert isinstance(element, Element)
    assert element.semantic_type == ElementSemanticType.TEXTBOX
    assert element.html_id == "short_description"
    assert recorder.get_elements(_PAGE_ID) == [element]
    assert len(publisher.of_type(ElementFound)) == 1
    assert len(publisher.of_type(ElementsCaptured)) == 1


def test_password_input_is_classified_as_sensitive() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.observe_elements(
        _SESSION_ID, _PAGE_ID, [_text_input(input_type="password", html_id="user_password")]
    )

    [element] = recorder.capture_elements(_PAGE_ID)

    assert element.semantic_type == ElementSemanticType.PASSWORD
    assert element.sensitivity_classification == SensitivityClassification.SENSITIVE


def test_sensitive_hint_overrides_classification_for_non_password_fields() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.observe_elements(
        _SESSION_ID, _PAGE_ID, [_text_input(html_id="cpf", is_sensitive_hint=True)]
    )

    [element] = recorder.capture_elements(_PAGE_ID)

    assert element.semantic_type == ElementSemanticType.TEXTBOX
    assert element.sensitivity_classification == SensitivityClassification.SENSITIVE


def test_role_takes_priority_over_tag_for_classification() -> None:
    recorder, _publisher, _log = _make_recorder()
    raw = RawElementObservation(
        frame_origin=_FRAME_ORIGIN, frame_selector=None, tag="div", role="grid"
    )
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [raw])

    [element] = recorder.capture_elements(_PAGE_ID)

    assert element.semantic_type == ElementSemanticType.GRID


def test_unknown_tag_without_role_is_classified_as_unknown() -> None:
    recorder, _publisher, _log = _make_recorder()
    raw = RawElementObservation(
        frame_origin=_FRAME_ORIGIN, frame_selector=None, tag="custom-widget"
    )
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [raw])

    [element] = recorder.capture_elements(_PAGE_ID)

    assert element.semantic_type == ElementSemanticType.UNKNOWN


def test_semantic_type_hint_overrides_heuristic() -> None:
    recorder, _publisher, _log = _make_recorder()
    raw = _text_input(semantic_type_hint=ElementSemanticType.RELATED_LIST)
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [raw])

    [element] = recorder.capture_elements(_PAGE_ID)

    assert element.semantic_type == ElementSemanticType.RELATED_LIST


@pytest.mark.parametrize(
    ("semantic_type_hint", "event_type"),
    [
        (ElementSemanticType.FORM, FormDetected),
        (ElementSemanticType.GRID, GridDetected),
        (ElementSemanticType.RELATED_LIST, RelatedListDetected),
    ],
)
def test_special_semantic_types_publish_detection_events(
    semantic_type_hint: ElementSemanticType, event_type: type
) -> None:
    recorder, publisher, _log = _make_recorder()
    raw = _text_input(semantic_type_hint=semantic_type_hint)
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [raw])

    recorder.capture_elements(_PAGE_ID)

    assert len(publisher.of_type(event_type)) == 1


def test_parent_index_resolves_to_parent_element_id() -> None:
    recorder, _publisher, _log = _make_recorder()
    parent_raw = RawElementObservation(
        frame_origin=_FRAME_ORIGIN, frame_selector=None, tag="form", html_id="incident_form"
    )
    child_raw = _text_input(parent_index=0)
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [parent_raw, child_raw])

    parent, child = recorder.capture_elements(_PAGE_ID)

    assert child.parent_element_id == parent.element_id


def test_revisiting_the_same_page_deduplicates_by_fingerprint() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input(disabled=False)])
    first = recorder.capture_elements(_PAGE_ID)[0]

    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input(disabled=True)])
    second = recorder.capture_elements(_PAGE_ID)[0]

    assert first.element_id == second.element_id
    assert second.disabled is True
    assert len(recorder.get_elements(_PAGE_ID)) == 1
    assert len(publisher.of_type(ElementFound)) == 1


def test_different_frames_get_different_frame_ids() -> None:
    recorder, _publisher, _log = _make_recorder()
    main = _text_input(frame_selector=None)
    nested = _text_input(frame_selector="iframe#gsft_main", html_id="nested_field")
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [main, nested])

    main_element, nested_element = recorder.capture_elements(_PAGE_ID)

    assert main_element.frame_id != nested_element.frame_id
    assert len(recorder.get_frames(_PAGE_ID)) == 2


# ----------------------------------------------------------------------
# get_element / find_element
# ----------------------------------------------------------------------


def test_get_element_returns_none_for_unknown_id() -> None:
    recorder, _publisher, _log = _make_recorder()

    assert recorder.get_element(UUID(int=999)) is None


def test_find_element_by_fingerprint() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input()])
    [element] = recorder.capture_elements(_PAGE_ID)

    assert element.fingerprint is not None
    assert recorder.find_element(_PAGE_ID, element.fingerprint) is element
    assert recorder.find_element(_PAGE_ID, "not-a-real-fingerprint") is None


# ----------------------------------------------------------------------
# update_element / remove_element
# ----------------------------------------------------------------------


def test_update_element_without_staged_observation_raises() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input()])
    [element] = recorder.capture_elements(_PAGE_ID)

    with pytest.raises(NoPendingElementsError):
        recorder.update_element(element.element_id.value)


def test_update_element_with_unknown_id_raises() -> None:
    recorder, _publisher, _log = _make_recorder()

    with pytest.raises(ElementNotFoundError):
        recorder.update_element(UUID(int=999))


def test_stage_element_update_applies_new_attributes() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input(label="Descrição")])
    [element] = recorder.capture_elements(_PAGE_ID)

    recorder.stage_element_update(element.element_id.value, _text_input(label="Descrição curta"))
    updated = recorder.update_element(element.element_id.value)

    assert updated.label == "Descrição curta"
    assert len(publisher.of_type(ElementUpdated)) == 1


def test_remove_element_clears_it_from_lookups_and_publishes() -> None:
    recorder, publisher, _log = _make_recorder()
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input()])
    [element] = recorder.capture_elements(_PAGE_ID)

    recorder.remove_element(element.element_id.value)

    assert recorder.get_element(element.element_id.value) is None
    assert recorder.get_elements(_PAGE_ID) == []
    assert len(publisher.of_type(ElementRemoved)) == 1


def test_remove_element_with_unknown_id_raises() -> None:
    recorder, _publisher, _log = _make_recorder()

    with pytest.raises(ElementNotFoundError):
        recorder.remove_element(UUID(int=999))


# ----------------------------------------------------------------------
# clear_page / get_statistics
# ----------------------------------------------------------------------


def test_clear_page_only_affects_the_given_page() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.observe_elements(_SESSION_ID, _PAGE_ID, [_text_input()])
    recorder.capture_elements(_PAGE_ID)
    recorder.observe_elements(_SESSION_ID, _OTHER_PAGE_ID, [_text_input(html_id="other")])
    recorder.capture_elements(_OTHER_PAGE_ID)

    recorder.clear_page(_PAGE_ID)

    assert recorder.get_elements(_PAGE_ID) == []
    assert recorder.get_frames(_PAGE_ID) == []
    assert len(recorder.get_elements(_OTHER_PAGE_ID)) == 1


def test_get_statistics_aggregates_by_semantic_type_and_sensitivity() -> None:
    recorder, _publisher, _log = _make_recorder()
    recorder.observe_elements(
        _SESSION_ID,
        _PAGE_ID,
        [
            _text_input(html_id="a"),
            _text_input(html_id="b", input_type="password"),
        ],
    )

    recorder.capture_elements(_PAGE_ID)
    stats = recorder.get_statistics()

    assert stats["total_elements"] == 2
    assert stats["pages_with_elements"] == 1
    assert stats["by_semantic_type"] == {"textbox": 1, "password": 1}
    assert stats["by_sensitivity_classification"] == {"none": 1, "sensitive": 1}
