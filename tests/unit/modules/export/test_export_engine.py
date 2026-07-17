"""Testes do ``ExportEngine`` (Module Specifications, Capítulo 9).

Diferente dos demais módulos centrais, este realmente grava arquivos —
os testes usam o fixture ``tmp_path`` do pytest como diretório de
saída, nunca tocando o sistema de arquivos real do projeto.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from snkb.domain.entities.element import Element
from snkb.domain.entities.frame import Frame
from snkb.domain.entities.page import Page
from snkb.domain.entities.screenshot import Screenshot
from snkb.domain.entities.selector import ElementSelectors
from snkb.domain.entities.session import Session
from snkb.domain.enums.element_semantic_type import ElementSemanticType
from snkb.domain.enums.screenshot_type import ScreenshotType
from snkb.domain.enums.selector_strategy_type import SelectorStrategyType
from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.events.export_events import ExportCompleted, ExportFailed, ReportCreated
from snkb.domain.exceptions.export_exceptions import ExportValidationError
from snkb.domain.value_objects.identifiers import (
    ElementId,
    FrameId,
    PageId,
    ScreenshotId,
    SessionId,
)
from snkb.domain.value_objects.selector_candidate import SelectorCandidate
from snkb.domain.value_objects.url import NormalizedUrl
from snkb.domain.value_objects.viewport import Resolution, Viewport
from snkb.modules.export.export_engine import ExportEngine
from snkb.shared.dtos.manifest_json import ManifestJsonModel
from snkb.shared.dtos.navigation_json import NavigationJsonModel
from snkb.shared.dtos.page_json import PageJsonModel
from snkb.shared.dtos.selectors_json import SelectorsJsonModel
from snkb.shared.dtos.session_json import SessionJsonModel
from snkb.shared.dtos.statistics_json import StatisticsJsonModel

_SESSION_ID = UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")
_PAGE_ID = UUID("1c2d3e4f-5a6b-47c8-89d0-1234567890ab")
_ELEMENT_ID = UUID("2c2d3e4f-5a6b-47c8-89d0-1234567890ab")
_FRAME_ID = FrameId(value=UUID("3c2d3e4f-5a6b-47c8-89d0-1234567890ab"))
_SCREENSHOT_ID = UUID("4c2d3e4f-5a6b-47c8-89d0-1234567890ab")
_INSTANCE_URL = "https://empresa.service-now.com"


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


class _FakeSessionManager:
    def __init__(self) -> None:
        self.sessions: dict[UUID, Session] = {}
        self.stats: dict[UUID, dict[str, object]] = {}

    def get_session(self, session_id: UUID) -> Session:
        return self.sessions[session_id]

    def get_statistics(self, session_id: UUID) -> dict[str, object]:
        return self.stats.get(session_id, {})


class _FakeNavigationRecorder:
    def __init__(self) -> None:
        self.session_id: UUID | None = None
        self.pages: list[Page] = []

    def export_navigation(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "session_id": str(self.session_id),
            "nodes": [
                {"page_id": str(page.page_id.value), "title": page.title, "url": page.url.value}
                for page in self.pages
            ],
            "edges": [],
            "timeline": [],
        }

    def get_page_history(self) -> list[Page]:
        return list(self.pages)


class _FakeElementRecorder:
    def __init__(self) -> None:
        self.elements_by_page: dict[UUID, list[Element]] = {}
        self.frames_by_page: dict[UUID, list[Frame]] = {}
        self.stats: dict[str, object] = {"total_elements": 0}

    def get_elements(self, page_id: UUID) -> list[Element]:
        return list(self.elements_by_page.get(page_id, []))

    def get_frames(self, page_id: UUID) -> list[Frame]:
        return list(self.frames_by_page.get(page_id, []))

    def get_statistics(self) -> dict[str, object]:
        return self.stats


class _FakeSelectorAnalyzer:
    def __init__(self) -> None:
        self.selectors_by_element: dict[UUID, ElementSelectors] = {}

    def get_all_selectors(self, element_id: UUID) -> ElementSelectors:
        cached = self.selectors_by_element.get(element_id)
        if cached is not None:
            return cached
        return ElementSelectors(element_id=ElementId(value=element_id), candidates=[])


class _FakeScreenshotEngine:
    def __init__(self) -> None:
        self.screenshots_by_page: dict[UUID, list[Screenshot]] = {}
        self.stats: dict[str, object] = {"total_screenshots": 0}

    def get_screenshots(self, page_id: UUID) -> list[Screenshot]:
        return list(self.screenshots_by_page.get(page_id, []))

    def statistics(self) -> dict[str, object]:
        return self.stats


def _make_full_session(session_id: UUID = _SESSION_ID) -> Session:
    return Session(
        session_id=SessionId(value=session_id),
        instance_url=_INSTANCE_URL,
        created_at=datetime(2026, 7, 17, 8, 55, 0, tzinfo=UTC),
        status=SessionStatus.COMPLETED,
        recording_start=datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC),
        recording_end=datetime(2026, 7, 17, 9, 30, 0, tzinfo=UTC),
        browser="Chromium",
        browser_version="126.0",
        operating_system="Windows 11",
        screen_resolution=Resolution(width=1920, height=1080),
        viewport=Viewport(width=1920, height=1080),
    )


def _make_page(page_id: UUID = _PAGE_ID, session_id: UUID = _SESSION_ID) -> Page:
    return Page(
        page_id=PageId(value=page_id),
        session_id=SessionId(value=session_id),
        name_original="incident_list",
        title="Lista de Incidentes",
        url=NormalizedUrl(value=f"{_INSTANCE_URL}/incident_list.do"),
        fingerprint="abc123",
        first_seen=datetime(2026, 7, 17, 9, 5, 0, tzinfo=UTC),
    )


def _make_element(element_id: UUID = _ELEMENT_ID, page_id: UUID = _PAGE_ID) -> Element:
    return Element(
        element_id=ElementId(value=element_id),
        page_id=PageId(value=page_id),
        frame_id=_FRAME_ID,
        semantic_type=ElementSemanticType.TEXTBOX,
        tag="input",
        html_id="short_description",
    )


def _make_selectors(element_id: UUID = _ELEMENT_ID) -> ElementSelectors:
    return ElementSelectors(
        element_id=ElementId(value=element_id),
        candidates=[
            SelectorCandidate(
                strategy=SelectorStrategyType.ID,
                value="#short_description",
                confidence_score=95,
                stability_score=80,
            ),
            SelectorCandidate(
                strategy=SelectorStrategyType.CSS,
                value="#short_description",
                confidence_score=50,
                stability_score=50,
            ),
        ],
    )


def _make_screenshot(
    screenshot_id: UUID = _SCREENSHOT_ID, page_id: UUID = _PAGE_ID, session_id: UUID = _SESSION_ID
) -> Screenshot:
    return Screenshot(
        screenshot_id=ScreenshotId(value=screenshot_id),
        session_id=SessionId(value=session_id),
        page_id=PageId(value=page_id),
        captured_at=datetime(2026, 7, 17, 9, 6, 0, tzinfo=UTC),
        capture_type=ScreenshotType.VIEWPORT,
        file_name=f"{page_id}_viewport_001.png",
        width=1920,
        height=1080,
    )


def _make_engine(
    tmp_path: Path,
    screenshot_bytes_provider: Callable[[UUID], bytes | None] | None = None,
) -> tuple[
    ExportEngine,
    _FakeSessionManager,
    _FakeNavigationRecorder,
    _FakeElementRecorder,
    _FakeSelectorAnalyzer,
    _FakeScreenshotEngine,
    _RecordingEventPublisher,
]:
    session_manager = _FakeSessionManager()
    navigation_recorder = _FakeNavigationRecorder()
    element_recorder = _FakeElementRecorder()
    selector_analyzer = _FakeSelectorAnalyzer()
    screenshot_engine = _FakeScreenshotEngine()
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()

    engine = ExportEngine(
        session_manager=session_manager,  # type: ignore[arg-type]
        navigation_recorder=navigation_recorder,  # type: ignore[arg-type]
        element_recorder=element_recorder,  # type: ignore[arg-type]
        selector_analyzer=selector_analyzer,  # type: ignore[arg-type]
        screenshot_engine=screenshot_engine,  # type: ignore[arg-type]
        event_publisher=publisher,  # type: ignore[arg-type]
        log_engine=log,  # type: ignore[arg-type]
        output_directory=tmp_path,
        now=lambda: datetime(2026, 7, 17, 10, 0, 0, tzinfo=UTC),
        screenshot_bytes_provider=screenshot_bytes_provider,
    )
    return (
        engine,
        session_manager,
        navigation_recorder,
        element_recorder,
        selector_analyzer,
        screenshot_engine,
        publisher,
    )


def _populate_full_fixture(
    session_manager: _FakeSessionManager,
    navigation_recorder: _FakeNavigationRecorder,
    element_recorder: _FakeElementRecorder,
    selector_analyzer: _FakeSelectorAnalyzer,
    screenshot_engine: _FakeScreenshotEngine,
) -> None:
    session_manager.sessions[_SESSION_ID] = _make_full_session()
    session_manager.stats[_SESSION_ID] = {"status": "completed", "warnings_count": 0}

    page = _make_page()
    navigation_recorder.session_id = _SESSION_ID
    navigation_recorder.pages = [page]

    element = _make_element()
    element_recorder.elements_by_page[_PAGE_ID] = [element]
    element_recorder.frames_by_page[_PAGE_ID] = [
        Frame(
            frame_id=_FRAME_ID,
            page_id=PageId(value=_PAGE_ID),
            origin=_INSTANCE_URL,
            selector=None,
        )
    ]
    element_recorder.stats = {"total_elements": 1}

    selector_analyzer.selectors_by_element[_ELEMENT_ID] = _make_selectors()

    screenshot_engine.screenshots_by_page[_PAGE_ID] = [_make_screenshot()]
    screenshot_engine.stats = {"total_screenshots": 1}


# ----------------------------------------------------------------------
# export_session
# ----------------------------------------------------------------------


def test_export_session_requires_complete_metadata(tmp_path: Path) -> None:
    engine, session_manager, *_ = _make_engine(tmp_path)
    session_manager.sessions[_SESSION_ID] = Session(
        session_id=SessionId(value=_SESSION_ID),
        instance_url=_INSTANCE_URL,
        created_at=datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC),
        status=SessionStatus.CREATED,
    )

    with pytest.raises(ExportValidationError):
        engine.export_session(_SESSION_ID)


def test_export_session_writes_valid_json(tmp_path: Path) -> None:
    engine, session_manager, *_ = _make_engine(tmp_path)
    session_manager.sessions[_SESSION_ID] = _make_full_session()

    path = engine.export_session(_SESSION_ID)

    assert path.is_file()
    model = SessionJsonModel.model_validate_json(path.read_text(encoding="utf-8"))
    assert model.recording_id == _SESSION_ID
    assert model.browser == "Chromium"


# ----------------------------------------------------------------------
# export_navigation
# ----------------------------------------------------------------------


def test_export_navigation_rejects_session_mismatch(tmp_path: Path) -> None:
    engine, _sm, navigation_recorder, *_ = _make_engine(tmp_path)
    navigation_recorder.session_id = UUID(int=999)

    with pytest.raises(ExportValidationError):
        engine.export_navigation(_SESSION_ID)


def test_export_navigation_writes_valid_json(tmp_path: Path) -> None:
    engine, _sm, navigation_recorder, *_ = _make_engine(tmp_path)
    navigation_recorder.session_id = _SESSION_ID
    navigation_recorder.pages = [_make_page()]

    path = engine.export_navigation(_SESSION_ID)

    model = NavigationJsonModel.model_validate_json(path.read_text(encoding="utf-8"))
    assert model.session_id == _SESSION_ID
    assert len(model.nodes) == 1


# ----------------------------------------------------------------------
# export_pages
# ----------------------------------------------------------------------


def test_export_pages_writes_page_and_screenshot_manifest(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, _publisher = _make_engine(tmp_path)
    _populate_full_fixture(sm, nav, elems, selectors, shots)

    written = engine.export_pages(_SESSION_ID)

    assert len(written) == 1
    page_model = PageJsonModel.model_validate_json(written[0].read_text(encoding="utf-8"))
    assert page_model.page_id == _PAGE_ID
    assert len(page_model.elements) == 1
    assert page_model.elements[0].selectors[0]["strategy"] == "id"
    assert page_model.screenshots == [_SCREENSHOT_ID]

    screenshots_manifest = tmp_path / str(_SESSION_ID) / "screenshots" / f"{_PAGE_ID}.json"
    assert screenshots_manifest.is_file()


def test_export_pages_skips_screenshot_manifest_when_no_screenshots(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, _shots, _publisher = _make_engine(tmp_path)
    sm.sessions[_SESSION_ID] = _make_full_session()
    nav.session_id = _SESSION_ID
    nav.pages = [_make_page()]

    engine.export_pages(_SESSION_ID)

    screenshots_manifest = tmp_path / str(_SESSION_ID) / "screenshots" / f"{_PAGE_ID}.json"
    assert not screenshots_manifest.exists()


def test_export_pages_writes_screenshot_bytes_when_provider_given(tmp_path: Path) -> None:
    written_bytes = {_SCREENSHOT_ID: b"\x89PNGfake"}
    engine, sm, nav, elems, selectors, shots, _publisher = _make_engine(
        tmp_path, screenshot_bytes_provider=lambda sid: written_bytes.get(sid)
    )
    _populate_full_fixture(sm, nav, elems, selectors, shots)

    engine.export_pages(_SESSION_ID)

    png_path = tmp_path / str(_SESSION_ID) / "screenshots" / f"{_PAGE_ID}_viewport_001.png"
    assert png_path.read_bytes() == b"\x89PNGfake"


# ----------------------------------------------------------------------
# export_selectors
# ----------------------------------------------------------------------


def test_export_selectors_splits_best_and_fallback(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, _publisher = _make_engine(tmp_path)
    _populate_full_fixture(sm, nav, elems, selectors, shots)

    path = engine.export_selectors(_SESSION_ID)

    model = SelectorsJsonModel.model_validate_json(path.read_text(encoding="utf-8"))
    assert len(model.elements) == 1
    entry = model.elements[0]
    assert entry.best_strategy is not None
    assert entry.best_strategy.strategy == "id"
    assert len(entry.fallback_strategies) == 1
    assert entry.fallback_strategies[0].strategy == "css"


# ----------------------------------------------------------------------
# export_statistics
# ----------------------------------------------------------------------


def test_export_statistics_aggregates_totals(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, _publisher = _make_engine(tmp_path)
    _populate_full_fixture(sm, nav, elems, selectors, shots)

    path = engine.export_statistics(_SESSION_ID)

    model = StatisticsJsonModel.model_validate_json(path.read_text(encoding="utf-8"))
    assert model.total_pages == 1
    assert model.total_elements == 1
    assert model.total_selectors == 2
    assert model.total_screenshots == 1


# ----------------------------------------------------------------------
# export_manifest
# ----------------------------------------------------------------------


def test_export_manifest_computes_checksums_and_excludes_tmp_files(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, _publisher = _make_engine(tmp_path)
    _populate_full_fixture(sm, nav, elems, selectors, shots)
    engine.export_session(_SESSION_ID)
    (tmp_path / str(_SESSION_ID) / "leftover.tmp").write_text("stale", encoding="utf-8")

    path = engine.export_manifest(_SESSION_ID)

    model = ManifestJsonModel.model_validate_json(path.read_text(encoding="utf-8"))
    paths = {entry.path for entry in model.files}
    assert "session.json" in paths
    assert "leftover.tmp" not in paths
    assert "manifest.json" not in paths


# ----------------------------------------------------------------------
# generate_report
# ----------------------------------------------------------------------


def test_generate_report_escapes_page_titles(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, publisher = _make_engine(tmp_path)
    sm.sessions[_SESSION_ID] = _make_full_session()
    nav.session_id = _SESSION_ID
    malicious_page = _make_page()
    malicious_page.title = "<script>alert(1)</script>"
    nav.pages = [malicious_page]

    path = engine.generate_report(_SESSION_ID)

    content = path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;" in content
    assert len(publisher.of_type(ReportCreated)) == 1


# ----------------------------------------------------------------------
# export() — pipeline completo
# ----------------------------------------------------------------------


def test_export_runs_the_full_pipeline_and_validates(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, publisher = _make_engine(tmp_path)
    _populate_full_fixture(sm, nav, elems, selectors, shots)

    output_dir = engine.export(_SESSION_ID)

    assert output_dir == tmp_path / str(_SESSION_ID)
    assert engine.validate(_SESSION_ID) is True
    completed = publisher.of_type(ExportCompleted)
    assert len(completed) == 1
    assert completed[0].output_directory == str(output_dir)


def test_export_publishes_failed_and_reraises_on_error(tmp_path: Path) -> None:
    engine, session_manager, *_rest, publisher = _make_engine(tmp_path)
    session_manager.sessions[_SESSION_ID] = Session(
        session_id=SessionId(value=_SESSION_ID),
        instance_url=_INSTANCE_URL,
        created_at=datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC),
        status=SessionStatus.CREATED,
    )

    with pytest.raises(ExportValidationError):
        engine.export(_SESSION_ID)

    assert len(publisher.of_type(ExportFailed)) == 1


# ----------------------------------------------------------------------
# validate() / clear_temp()
# ----------------------------------------------------------------------


def test_validate_detects_tampered_file(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, _publisher = _make_engine(tmp_path)
    _populate_full_fixture(sm, nav, elems, selectors, shots)
    engine.export(_SESSION_ID)

    (tmp_path / str(_SESSION_ID) / "session.json").write_text("{}", encoding="utf-8")

    assert engine.validate(_SESSION_ID) is False


def test_validate_returns_false_when_nothing_was_exported(tmp_path: Path) -> None:
    engine, *_rest = _make_engine(tmp_path)

    assert engine.validate(_SESSION_ID) is False


def test_clear_temp_removes_leftover_files_only(tmp_path: Path) -> None:
    engine, sm, nav, elems, selectors, shots, _publisher = _make_engine(tmp_path)
    _populate_full_fixture(sm, nav, elems, selectors, shots)
    engine.export_session(_SESSION_ID)
    session_dir = tmp_path / str(_SESSION_ID)
    (session_dir / "leftover.tmp").write_text("stale", encoding="utf-8")

    engine.clear_temp(_SESSION_ID)

    assert not (session_dir / "leftover.tmp").exists()
    assert (session_dir / "session.json").exists()
