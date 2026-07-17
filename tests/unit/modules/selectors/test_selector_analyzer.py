"""Testes do ``SelectorAnalyzer`` — puros, sem I/O (Module
Specifications, Capítulo 7)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from uuid import UUID

import pytest

from snkb.domain.entities.element import Element
from snkb.domain.enums.element_semantic_type import ElementSemanticType
from snkb.domain.enums.selector_strategy_type import SelectorStrategyType
from snkb.domain.events.selector_events import (
    LowConfidenceSelector,
    SelectorConflict,
    SelectorRemoved,
    SelectorsReady,
    SelectorUpdated,
)
from snkb.domain.exceptions.element_exceptions import ElementNotFoundError
from snkb.domain.exceptions.selector_exceptions import PageSessionNotRegisteredError
from snkb.domain.value_objects.identifiers import ElementId, FrameId, PageId
from snkb.domain.value_objects.selector_candidate import SelectorCandidate
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer

_SESSION_ID = UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")
_PAGE_ID = UUID("1c2d3e4f-5a6b-47c8-89d0-1234567890ab")
_FRAME_ID = FrameId(value=UUID("3c2d3e4f-5a6b-47c8-89d0-1234567890ab"))


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


class _FakeElementRecorder:
    def __init__(self) -> None:
        self.elements: dict[UUID, Element] = {}

    def add(self, element: Element) -> Element:
        self.elements[element.element_id.value] = element
        return element

    def get_element(self, element_id: UUID) -> Element | None:
        return self.elements.get(element_id)

    def get_elements(self, page_id: UUID) -> list[Element]:
        return [element for element in self.elements.values() if element.page_id.value == page_id]


def _sequential_uuid_factory() -> Callable[[], UUID]:
    counter = itertools.count(1)
    return lambda: UUID(int=next(counter))


def _make_element(element_id: UUID, page_id: UUID = _PAGE_ID, **overrides: object) -> Element:
    base: dict[str, object] = {
        "element_id": ElementId(value=element_id),
        "page_id": PageId(value=page_id),
        "frame_id": _FRAME_ID,
        "semantic_type": ElementSemanticType.TEXTBOX,
        "tag": "input",
        "html_id": "short_description",
        "name": "short_description",
        "accessible_name": "Descrição curta",
        "role": "textbox",
    }
    base.update(overrides)
    return Element(**base)  # type: ignore[arg-type]


def _make_analyzer() -> tuple[SelectorAnalyzer, _FakeElementRecorder, _RecordingEventPublisher]:
    element_recorder = _FakeElementRecorder()
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()
    analyzer = SelectorAnalyzer(
        element_recorder=element_recorder, event_publisher=publisher, log_engine=log
    )
    return analyzer, element_recorder, publisher


_new_id = _sequential_uuid_factory()


# ----------------------------------------------------------------------
# Pré-condições
# ----------------------------------------------------------------------


def test_analyze_unknown_element_raises() -> None:
    analyzer, _elements, _publisher = _make_analyzer()

    with pytest.raises(ElementNotFoundError):
        analyzer.analyze(UUID(int=999))


def test_analyze_without_registered_session_raises() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))

    with pytest.raises(PageSessionNotRegisteredError):
        analyzer.analyze(element.element_id.value)


# ----------------------------------------------------------------------
# generate()
# ----------------------------------------------------------------------


def test_generate_produces_a_candidate_per_available_signal() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))

    candidates = analyzer.generate(element.element_id.value)

    strategies = {candidate.strategy for candidate in candidates}
    assert strategies == {
        SelectorStrategyType.ID,
        SelectorStrategyType.NAME,
        SelectorStrategyType.ARIA_LABEL,
        SelectorStrategyType.ROLE,
        SelectorStrategyType.CSS,
        SelectorStrategyType.XPATH_RELATIVE,
        SelectorStrategyType.XPATH_ABSOLUTE,
    }


def test_generate_ranks_id_strategy_highest_when_unique() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))

    candidates = analyzer.generate(element.element_id.value)

    assert candidates[0].strategy == SelectorStrategyType.ID
    assert candidates[0].value == "#short_description"
    assert candidates[0].uniqueness_count == 1


def test_duplicate_html_id_lowers_confidence_and_uniqueness_count() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    first = elements.add(_make_element(_new_id(), html_id="duplicate"))
    elements.add(_make_element(_new_id(), html_id="duplicate"))

    candidates = analyzer.generate(first.element_id.value)

    id_candidate = next(c for c in candidates if c.strategy == SelectorStrategyType.ID)
    assert id_candidate.uniqueness_count == 2
    assert id_candidate.confidence_score < 95


def test_element_with_only_a_tag_still_gets_fallback_candidates() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    element = elements.add(
        _make_element(
            _new_id(),
            html_id=None,
            name=None,
            accessible_name=None,
            label=None,
            role=None,
            tag="div",
        )
    )

    candidates = analyzer.generate(element.element_id.value)

    strategies = {candidate.strategy for candidate in candidates}
    assert strategies == {
        SelectorStrategyType.CSS,
        SelectorStrategyType.XPATH_RELATIVE,
        SelectorStrategyType.XPATH_ABSOLUTE,
    }
    xpath_relative = next(
        c for c in candidates if c.strategy == SelectorStrategyType.XPATH_RELATIVE
    )
    assert xpath_relative.value == "//div"


def test_absolute_xpath_walks_the_parent_chain() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    grandparent = elements.add(_make_element(_new_id(), tag="form", html_id=None, name=None))
    parent = elements.add(
        _make_element(
            _new_id(), tag="div", html_id=None, name=None, parent_element_id=grandparent.element_id
        )
    )
    child = elements.add(
        _make_element(
            _new_id(), tag="input", html_id=None, name=None, parent_element_id=parent.element_id
        )
    )

    candidates = analyzer.generate(child.element_id.value)

    xpath_absolute = next(
        c for c in candidates if c.strategy == SelectorStrategyType.XPATH_ABSOLUTE
    )
    assert xpath_absolute.value == "/form/div/input"


# ----------------------------------------------------------------------
# calculate_score
# ----------------------------------------------------------------------


def test_calculate_score_blends_strategy_weight_confidence_and_stability() -> None:
    analyzer, _elements, _publisher = _make_analyzer()
    candidate = SelectorCandidate(
        strategy=SelectorStrategyType.ID, value="#x", confidence_score=95, stability_score=80
    )

    score = analyzer.calculate_score(candidate)

    assert score == round(100 * 0.4 + 95 * 0.4 + 80 * 0.2)


# ----------------------------------------------------------------------
# analyze() — eventos
# ----------------------------------------------------------------------


def test_analyze_publishes_selectors_ready() -> None:
    analyzer, elements, publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))
    analyzer.register_session_for_page(_SESSION_ID, _PAGE_ID)

    analyzer.analyze(element.element_id.value)

    assert len(publisher.of_type(SelectorsReady)) == 1


def test_analyze_publishes_low_confidence_selector_for_weak_elements() -> None:
    analyzer, elements, publisher = _make_analyzer()
    element = elements.add(
        _make_element(
            _new_id(), html_id=None, name=None, accessible_name=None, label=None, role=None
        )
    )
    analyzer.register_session_for_page(_SESSION_ID, _PAGE_ID)

    analyzer.analyze(element.element_id.value)

    assert len(publisher.of_type(LowConfidenceSelector)) == 1


def test_analyze_publishes_selector_conflict_for_duplicate_ids() -> None:
    analyzer, elements, publisher = _make_analyzer()
    first = elements.add(_make_element(_new_id(), html_id="duplicate"))
    elements.add(_make_element(_new_id(), html_id="duplicate"))
    analyzer.register_session_for_page(_SESSION_ID, _PAGE_ID)

    analyzer.analyze(first.element_id.value)

    assert len(publisher.of_type(SelectorConflict)) == 1


# ----------------------------------------------------------------------
# get_best_selector / get_all_selectors
# ----------------------------------------------------------------------


def test_get_all_selectors_lazily_analyzes_when_not_cached() -> None:
    analyzer, elements, publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))
    analyzer.register_session_for_page(_SESSION_ID, _PAGE_ID)

    selectors = analyzer.get_all_selectors(element.element_id.value)

    assert selectors.element_id == element.element_id
    assert len(publisher.of_type(SelectorsReady)) == 1


def test_get_best_selector_returns_the_top_ranked_candidate() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))
    analyzer.register_session_for_page(_SESSION_ID, _PAGE_ID)

    best = analyzer.get_best_selector(element.element_id.value)

    assert best is not None
    assert best.strategy == SelectorStrategyType.ID


# ----------------------------------------------------------------------
# validate_selector
# ----------------------------------------------------------------------


def test_validate_selector_matches_id_candidate_to_element() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))
    valid = SelectorCandidate(
        strategy=SelectorStrategyType.ID,
        value="#short_description",
        confidence_score=90,
        stability_score=80,
    )
    invalid = SelectorCandidate(
        strategy=SelectorStrategyType.ID,
        value="#something_else",
        confidence_score=90,
        stability_score=80,
    )

    assert analyzer.validate_selector(element.element_id.value, valid) is True
    assert analyzer.validate_selector(element.element_id.value, invalid) is False


def test_validate_selector_for_unknown_element_is_false() -> None:
    analyzer, _elements, _publisher = _make_analyzer()
    candidate = SelectorCandidate(
        strategy=SelectorStrategyType.CSS, value="div", confidence_score=50, stability_score=50
    )

    assert analyzer.validate_selector(UUID(int=999), candidate) is False


# ----------------------------------------------------------------------
# update_selector / remove_selector
# ----------------------------------------------------------------------


def test_update_selector_recomputes_and_publishes() -> None:
    analyzer, elements, publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))
    analyzer.register_session_for_page(_SESSION_ID, _PAGE_ID)
    analyzer.analyze(element.element_id.value)

    element.html_id = "new_id"
    updated = analyzer.update_selector(element.element_id.value)

    assert updated.best_candidate is not None
    assert updated.best_candidate.value == "#new_id"
    assert len(publisher.of_type(SelectorUpdated)) == 1


def test_remove_selector_drops_only_the_given_strategy() -> None:
    analyzer, elements, publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))
    analyzer.register_session_for_page(_SESSION_ID, _PAGE_ID)
    analyzer.analyze(element.element_id.value)

    analyzer.remove_selector(element.element_id.value, SelectorStrategyType.ID.value)

    remaining = analyzer.get_all_selectors(element.element_id.value)
    assert all(candidate.strategy != SelectorStrategyType.ID for candidate in remaining.candidates)
    assert len(publisher.of_type(SelectorRemoved)) == 1


def test_remove_selector_for_unanalyzed_element_raises() -> None:
    analyzer, elements, _publisher = _make_analyzer()
    element = elements.add(_make_element(_new_id()))

    with pytest.raises(ElementNotFoundError):
        analyzer.remove_selector(element.element_id.value, SelectorStrategyType.ID.value)
