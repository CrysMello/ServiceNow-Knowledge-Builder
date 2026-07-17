"""Testes do ``BrowserDataCollector`` (Module Specifications — ponte
Playwright ↔ Element Recorder/Selector Analyzer/Screenshot Engine, ADR
0013).

Usa os módulos de dados **reais** (Session Manager, Navigation
Recorder, Element Recorder, Selector Analyzer, Screenshot Engine —
todos síncronos, sem I/O, já testados isoladamente) e um duplo de
teste de ``Page``/``Frame`` do Playwright — nenhum destes testes abre
um navegador real (isso fica a cargo de
``tests/integration/test_browser_data_collector_integration.py``).
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from snkb.application.services.application_controller import (
    InMemoryEventBus,
    InMemoryScreenshotStore,
)
from snkb.domain.events.browser_events import PageChanged
from snkb.domain.events.element_events import ElementsCaptured
from snkb.domain.events.screenshot_events import ScreenshotCreated
from snkb.domain.events.selector_events import SelectorsReady
from snkb.domain.events.system_events import ErrorOccurred
from snkb.domain.exceptions.collector_exceptions import CollectorNotActiveError
from snkb.infrastructure.browser.browser_data_collector import BrowserDataCollector
from snkb.modules.elements.element_recorder import ElementRecorder
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.modules.screenshots.screenshot_engine import ScreenshotEngine
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer
from snkb.modules.session.session_manager import SessionManager
from snkb.shared.dtos.app_config import AppConfig, CapturePolicyModel

_SESSION_URL = "https://empresa.service-now.com/home"
_TAB_ID = "tab-1"


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


class _FakeFrame:
    def __init__(
        self,
        url: str,
        name: str = "",
        elements: list[dict[str, object]] | None = None,
        eval_error: Exception | None = None,
    ) -> None:
        self.url = url
        self.name = name
        self._elements = elements if elements is not None else []
        self.eval_error = eval_error
        self.eval_calls = 0

    async def evaluate(self, _script: str, _arg: object = None) -> list[dict[str, object]]:
        self.eval_calls += 1
        if self.eval_error is not None:
            raise self.eval_error
        return self._elements


class _FakeBrowser:
    def __init__(self, version: str = "120.0.0.0") -> None:
        self.version = version


class _FakeContext:
    def __init__(self, browser: _FakeBrowser | None) -> None:
        self.browser = browser


class _FakePage:
    def __init__(
        self,
        url: str = _SESSION_URL,
        elements: list[dict[str, object]] | None = None,
        title: str = "Home",
        screenshot_bytes: bytes = b"\x89PNGfake",
        screenshot_error: Exception | None = None,
        wait_for_load_error: Exception | None = None,
        title_error: Exception | None = None,
        closed: bool = False,
        extra_frames: list[_FakeFrame] | None = None,
    ) -> None:
        self.main_frame = _FakeFrame(url=url, elements=elements or [])
        self.frames = [self.main_frame, *(extra_frames or [])]
        self._title = title
        self._title_error = title_error
        self.screenshot_bytes = screenshot_bytes
        self.screenshot_error = screenshot_error
        self.wait_for_load_error = wait_for_load_error
        self._closed = closed
        self.viewport_size = {"width": 1024, "height": 768}
        self.context = _FakeContext(_FakeBrowser())
        self.screenshot_calls: list[dict[str, object]] = []

    def is_closed(self) -> bool:
        return self._closed

    async def title(self) -> str:
        if self._title_error is not None:
            raise self._title_error
        return self._title

    async def wait_for_load_state(self, _state: str, timeout: float | None = None) -> None:
        if self.wait_for_load_error is not None:
            raise self.wait_for_load_error

    async def screenshot(self, *, type: str = "png", full_page: bool = False) -> bytes:
        self.screenshot_calls.append({"type": type, "full_page": full_page})
        if self.screenshot_error is not None:
            raise self.screenshot_error
        return self.screenshot_bytes


class _FakeBrowserManager:
    def __init__(self, page: _FakePage | None) -> None:
        self.page = page

    def current_page(self) -> object:
        return self.page


def _element_dict(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "tag": "button",
        "role": None,
        "inputType": None,
        "accessibleName": "Novo",
        "label": None,
        "placeholder": None,
        "htmlId": "sysverb_new",
        "name": None,
        "classes": [],
        "required": False,
        "readonly": False,
        "disabled": False,
        "visible": True,
        "isSensitiveHint": False,
        "parentIndex": None,
    }
    base.update(overrides)
    return base


class _Harness:
    def __init__(self, capture_policy: CapturePolicyModel | None = None) -> None:
        self.log_engine = _RecordingLogEngine()
        self.event_bus = InMemoryEventBus(self.log_engine)
        self.screenshot_store = InMemoryScreenshotStore()
        self.session_manager = SessionManager(
            event_publisher=self.event_bus, log_engine=self.log_engine
        )
        self.navigation_recorder = NavigationRecorder(
            event_publisher=self.event_bus, log_engine=self.log_engine
        )
        self.element_recorder = ElementRecorder(
            event_publisher=self.event_bus, log_engine=self.log_engine
        )
        self.selector_analyzer = SelectorAnalyzer(
            element_recorder=self.element_recorder,
            event_publisher=self.event_bus,
            log_engine=self.log_engine,
        )
        self.screenshot_engine = ScreenshotEngine(
            event_publisher=self.event_bus,
            log_engine=self.log_engine,
            capture_policy=capture_policy or CapturePolicyModel(),
        )
        self.config = AppConfig(
            instance_url=_SESSION_URL,
            output_directory="exports",
            capture_policy=capture_policy or CapturePolicyModel(),
        )

    def make_collector(self, page: _FakePage | None) -> BrowserDataCollector:
        return BrowserDataCollector(
            browser_manager=_FakeBrowserManager(page),  # type: ignore[arg-type]
            navigation_recorder=self.navigation_recorder,  # type: ignore[arg-type]
            element_recorder=self.element_recorder,
            selector_analyzer=self.selector_analyzer,
            screenshot_engine=self.screenshot_engine,
            session_manager=self.session_manager,
            event_bus=self.event_bus,  # type: ignore[arg-type]
            log_engine=self.log_engine,
            screenshot_store=self.screenshot_store,  # type: ignore[arg-type]
            config=self.config,
        )

    def prepare_session_and_page(self, url: str = _SESSION_URL, tab_id: str = _TAB_ID) -> UUID:
        session = self.session_manager.create_session(url)
        session_id = session.session_id.value
        self.session_manager.mark_preparing(session_id)
        self.session_manager.mark_waiting_authentication(session_id)
        self.session_manager.mark_ready(session_id)
        self.session_manager.start_session(session_id)
        self.navigation_recorder.start(session_id)
        self.navigation_recorder.observe_navigation(tab_id=tab_id, url=url)
        self.navigation_recorder.capture_page()
        return session_id


def _make_harness(capture_policy: CapturePolicyModel | None = None) -> _Harness:
    return _Harness(capture_policy)


# ----------------------------------------------------------------------
# start / stop
# ----------------------------------------------------------------------


async def test_capture_current_page_without_start_raises() -> None:
    harness = _make_harness()
    collector = harness.make_collector(_FakePage())

    with pytest.raises(CollectorNotActiveError):
        await collector.capture_current_page()


async def test_stop_without_start_raises() -> None:
    harness = _make_harness()
    collector = harness.make_collector(_FakePage())

    with pytest.raises(CollectorNotActiveError):
        await collector.stop()


async def test_start_collects_session_metadata() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    collector = harness.make_collector(_FakePage())

    await collector.start(session_id)

    session = harness.session_manager.get_session(session_id)
    assert session.browser == "Chromium"
    assert session.browser_version == "120.0.0.0"
    assert session.operating_system is not None
    assert session.screen_resolution is not None
    assert session.viewport is not None

    await collector.stop()


async def test_start_twice_is_idempotent() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    collector = harness.make_collector(_FakePage())

    await collector.start(session_id)
    await collector.start(session_id)  # não deve levantar nem assinar duas vezes

    await collector.stop()


# ----------------------------------------------------------------------
# Captura de página / normalização
# ----------------------------------------------------------------------


async def test_capture_current_page_collects_normalized_elements() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    page = _FakePage(
        elements=[
            _element_dict(tag="button", htmlId="sysverb_new", accessibleName="New"),
            _element_dict(
                tag="input",
                inputType="text",
                htmlId=None,
                name="description",
                accessibleName="Description",
            ),
            _element_dict(tag="a", htmlId=None, accessibleName="Test Plan"),
        ]
    )
    collector = harness.make_collector(page)
    await collector.start(session_id)

    result = await collector.capture_current_page()

    assert result is not None
    assert result.element_count == 3
    assert result.new_element_count == 3
    assert result.screenshot_id is not None

    nav_page = harness.navigation_recorder.get_current_page()
    assert nav_page is not None
    elements = harness.element_recorder.get_elements(nav_page.page_id.value)
    assert len(elements) == 3
    tags = {element.tag for element in elements}
    assert tags == {"button", "input", "a"}

    await collector.stop()


async def test_capture_publishes_downstream_events() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    page = _FakePage(elements=[_element_dict()])
    collector = harness.make_collector(page)
    received: list[object] = []
    harness.event_bus.subscribe(received.append)
    await collector.start(session_id)

    await collector.capture_current_page()

    assert any(isinstance(event, ElementsCaptured) for event in received)
    assert any(isinstance(event, SelectorsReady) for event in received)
    assert any(isinstance(event, ScreenshotCreated) for event in received)

    await collector.stop()


async def test_screenshot_bytes_are_stored_for_export_engine() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    page = _FakePage(elements=[_element_dict()], screenshot_bytes=b"\x89PNGreal")
    collector = harness.make_collector(page)
    await collector.start(session_id)

    result = await collector.capture_current_page()

    assert result is not None
    assert result.screenshot_id is not None
    assert harness.screenshot_store.get(result.screenshot_id) == b"\x89PNGreal"

    await collector.stop()


# ----------------------------------------------------------------------
# Deduplicação
# ----------------------------------------------------------------------


async def test_capture_deduplicates_identical_content() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    elements = [_element_dict()]
    page = _FakePage(elements=elements)
    collector = harness.make_collector(page)
    await collector.start(session_id)

    first = await collector.capture_current_page()
    second = await collector.capture_current_page()

    assert first is not None
    assert second is None

    await collector.stop()


async def test_capture_reprocesses_when_content_changes() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    page = _FakePage(elements=[_element_dict(htmlId="a")])
    collector = harness.make_collector(page)
    await collector.start(session_id)

    first = await collector.capture_current_page()
    page.main_frame._elements = [_element_dict(htmlId="b")]
    second = await collector.capture_current_page()

    assert first is not None
    assert second is not None
    assert second.element_count == 2

    await collector.stop()


# ----------------------------------------------------------------------
# Erros e resiliência
# ----------------------------------------------------------------------


async def test_dom_collection_error_is_reported_without_crashing() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    page = _FakePage()
    page.main_frame.eval_error = PlaywrightError("DOM indisponível")
    collector = harness.make_collector(page)
    received: list[object] = []
    harness.event_bus.subscribe(received.append)
    await collector.start(session_id)

    result = await collector.capture_current_page()

    assert result is None
    assert any(isinstance(event, ErrorOccurred) for event in received)

    await collector.stop()


async def test_screenshot_error_does_not_prevent_element_capture() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    page = _FakePage(
        elements=[_element_dict()], screenshot_error=PlaywrightError("Falha ao capturar tela")
    )
    collector = harness.make_collector(page)
    await collector.start(session_id)

    result = await collector.capture_current_page()

    assert result is not None
    assert result.screenshot_id is None
    assert any("screenshot" in warning.lower() for warning in result.warnings)

    await collector.stop()


async def test_partial_page_load_still_captures_with_a_warning() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    page = _FakePage(
        elements=[_element_dict()],
        wait_for_load_error=PlaywrightTimeoutError("Timeout aguardando domcontentloaded"),
    )
    collector = harness.make_collector(page)
    await collector.start(session_id)

    result = await collector.capture_current_page()

    assert result is not None
    assert any("domcontentloaded" in warning.lower() for warning in result.warnings)

    await collector.stop()


async def test_inaccessible_frame_does_not_abort_the_whole_capture() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    broken_frame = _FakeFrame(
        url="https://empresa.service-now.com/frame",
        eval_error=PlaywrightError("Frame cross-origin"),
    )
    page = _FakePage(elements=[_element_dict()], extra_frames=[broken_frame])
    collector = harness.make_collector(page)
    await collector.start(session_id)

    result = await collector.capture_current_page()

    assert result is not None
    assert result.element_count == 1  # só o frame principal, o outro falhou
    assert any("frame" in warning.lower() for warning in result.warnings)

    await collector.stop()


async def test_capture_with_no_page_returns_none() -> None:
    harness = _make_harness()
    session_id = harness.prepare_session_and_page()
    collector = harness.make_collector(None)
    await collector.start(session_id)

    result = await collector.capture_current_page()

    assert result is None

    await collector.stop()


# ----------------------------------------------------------------------
# Estabilidade / debounce / encerramento com tarefa pendente
# ----------------------------------------------------------------------


async def test_rapid_page_changes_eventually_force_a_capture_within_max_wait() -> None:
    harness = _make_harness(
        capture_policy=CapturePolicyModel(
            page_stability_seconds=0.05, page_stability_max_wait_seconds=0.15
        )
    )
    session_id = harness.prepare_session_and_page()
    page = _FakePage(elements=[_element_dict()])
    collector = harness.make_collector(page)
    await collector.start(session_id)

    deadline = asyncio.get_running_loop().time() + 0.5
    while asyncio.get_running_loop().time() < deadline:
        harness.event_bus.publish(
            PageChanged(session_id=session_id, url=_SESSION_URL, tab_id=_TAB_ID)
        )
        await asyncio.sleep(0.02)
        nav_page = harness.navigation_recorder.get_current_page()
        if nav_page is not None and harness.element_recorder.get_elements(nav_page.page_id.value):
            break

    nav_page = harness.navigation_recorder.get_current_page()
    assert nav_page is not None
    assert harness.element_recorder.get_elements(nav_page.page_id.value) != []

    await collector.stop()


async def test_stop_awaits_pending_capture_task() -> None:
    harness = _make_harness(
        capture_policy=CapturePolicyModel(
            page_stability_seconds=0.05, page_stability_max_wait_seconds=0.2
        )
    )
    session_id = harness.prepare_session_and_page()
    page = _FakePage(elements=[_element_dict()])
    collector = harness.make_collector(page)
    await collector.start(session_id)

    harness.event_bus.publish(PageChanged(session_id=session_id, url=_SESSION_URL, tab_id=_TAB_ID))

    await collector.stop()  # não deve travar nem deixar a tarefa órfã

    nav_page = harness.navigation_recorder.get_current_page()
    assert nav_page is not None
    # A parada faz uma captura final — os elementos devem estar presentes.
    assert harness.element_recorder.get_elements(nav_page.page_id.value) != []
