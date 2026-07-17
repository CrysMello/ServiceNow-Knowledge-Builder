"""Teste de integração real do Browser Data Collector: Chromium
headless de verdade, contra um servidor HTTP local com três elementos
conhecidos (botão, input e link — AI Coding Standards, seção 19: nunca
a internet ou uma instância real).

Requer ``playwright install chromium``. Se os binários do navegador
não estiverem instalados, o teste é pulado — a lógica de orquestração
já é coberta pelos duplos de teste em
``tests/unit/infrastructure/browser/test_browser_data_collector.py``.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from uuid import uuid4

import pytest

from snkb.application.services.application_controller import (
    InMemoryEventBus,
    InMemoryScreenshotStore,
)
from snkb.infrastructure.browser.browser_data_collector import BrowserDataCollector
from snkb.infrastructure.browser.browser_manager import PlaywrightBrowserManager
from snkb.modules.elements.element_recorder import ElementRecorder
from snkb.modules.export.export_engine import ExportEngine
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.modules.screenshots.screenshot_engine import ScreenshotEngine
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer
from snkb.modules.session.session_manager import SessionManager
from snkb.shared.dtos.app_config import AppConfig, CapturePolicyModel

_PAGE_HTML = """
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Pagina de Teste</title></head>
<body>
  <button id="create">New</button>
  <input name="description" aria-label="Description">
  <a href="/test-plan">Test Plan</a>
</body>
</html>
"""


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


@pytest.fixture
def local_http_server(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "index.html").write_text(_PAGE_HTML, encoding="utf-8")
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


async def test_collector_captures_real_elements_selectors_and_screenshot(
    tmp_path: Path, local_http_server: str
) -> None:
    config = AppConfig(
        instance_url=local_http_server,
        output_directory=tmp_path / "exports",
        headless=True,
        capture_policy=CapturePolicyModel(),
    )
    log_engine = _RecordingLogEngine()
    event_bus = InMemoryEventBus(log_engine)
    screenshot_store = InMemoryScreenshotStore()

    session_manager = SessionManager(event_publisher=event_bus, log_engine=log_engine)
    navigation_recorder = NavigationRecorder(event_publisher=event_bus, log_engine=log_engine)
    element_recorder = ElementRecorder(event_publisher=event_bus, log_engine=log_engine)
    selector_analyzer = SelectorAnalyzer(
        element_recorder=element_recorder, event_publisher=event_bus, log_engine=log_engine
    )
    screenshot_engine = ScreenshotEngine(
        event_publisher=event_bus, log_engine=log_engine, capture_policy=config.capture_policy
    )
    export_engine = ExportEngine(
        session_manager=session_manager,
        navigation_recorder=navigation_recorder,
        element_recorder=element_recorder,
        selector_analyzer=selector_analyzer,
        screenshot_engine=screenshot_engine,
        event_publisher=event_bus,
        log_engine=log_engine,
        output_directory=config.output_directory,
        screenshot_bytes_provider=screenshot_store.get,
    )

    browser_manager = PlaywrightBrowserManager(
        session_id=uuid4(), config=config, event_publisher=event_bus, log_engine=log_engine
    )
    try:
        await browser_manager.initialize()
    except Exception as error:  # noqa: BLE001 — ambiente sem Chromium instalado.
        pytest.skip(f"Chromium indisponível para o teste de integração: {error}")

    try:
        await browser_manager.open_url(local_http_server)

        session = session_manager.create_session(local_http_server)
        session_id = session.session_id.value
        session_manager.mark_preparing(session_id)
        session_manager.mark_waiting_authentication(session_id)
        session_manager.mark_ready(session_id)
        session_manager.start_session(session_id)

        navigation_recorder.start(session_id)
        navigation_recorder.observe_navigation(tab_id="tab-1", url=local_http_server)
        page = navigation_recorder.capture_page()

        collector = BrowserDataCollector(
            browser_manager=browser_manager,
            navigation_recorder=navigation_recorder,  # type: ignore[arg-type]
            element_recorder=element_recorder,
            selector_analyzer=selector_analyzer,
            screenshot_engine=screenshot_engine,
            session_manager=session_manager,
            event_bus=event_bus,  # type: ignore[arg-type]
            log_engine=log_engine,
            screenshot_store=screenshot_store,
            config=config,
        )
        await collector.start(session_id)
        result = await collector.capture_current_page()

        assert result is not None
        assert result.element_count == 3
        assert result.screenshot_id is not None

        elements = element_recorder.get_elements(page.page_id.value)
        tags = {element.tag for element in elements}
        assert tags == {"button", "input", "a"}

        html_ids = {element.html_id for element in elements}
        assert "create" in html_ids

        for element in elements:
            selectors = selector_analyzer.get_all_selectors(element.element_id.value)
            assert selectors.candidates != []

        assert screenshot_store.get(result.screenshot_id) is not None

        await collector.stop()
        navigation_recorder.stop()
        session_manager.finish_session(session_id)

        output_dir = export_engine.export(session_id)
        assert export_engine.validate(session_id) is True
        assert (output_dir / "session.json").is_file()
        assert (output_dir / "selectors.json").is_file()
        assert list((output_dir / "pages").glob("*.json"))
        assert list((output_dir / "screenshots").glob("*.png"))
    finally:
        await browser_manager.close()
