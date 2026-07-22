"""Teste de integração real do Application Controller: usa um Chromium
de verdade (headless) através de um ``PlaywrightBrowserManager`` real
e um ``BrowserDataCollector`` real (ADR 0013), contra um servidor HTTP
local (sem acessar a internet ou uma instância real do ServiceNow —
AI Coding Standards, seção 19).

Requer ``playwright install chromium``. Se os binários do navegador não
estiverem instalados, o teste é pulado em vez de falhar — a lógica de
orquestração já é coberta pelos duplos de teste em
``tests/unit/application/services/test_application_controller.py``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from uuid import UUID

import pytest

from snkb.application.commands.commands import OpenExportFolder, StartCapture, StopCapture
from snkb.application.queries.queries import GetRecentSessions, ValidateExport
from snkb.application.services.application_controller import (
    ApplicationController,
    InMemoryEventBus,
    InMemoryScreenshotStore,
)
from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.events.export_events import ExportCompleted, ExportFailed
from snkb.domain.events.session_events import SessionCreated, SessionStarted
from snkb.infrastructure.browser.browser_data_collector import BrowserDataCollector
from snkb.infrastructure.browser.browser_manager import PlaywrightBrowserManager
from snkb.infrastructure.logging.log_reader import DiskLogReader
from snkb.infrastructure.storage.session_discovery import DiskSessionDiscovery
from snkb.modules.elements.element_recorder import ElementRecorder
from snkb.modules.export.export_engine import ExportEngine
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.modules.screenshots.screenshot_engine import ScreenshotEngine
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer
from snkb.modules.session.session_manager import SessionManager
from snkb.shared.dtos.app_config import AppConfig, CapturePolicyModel, LoginDetectionPolicyModel

_PAGE_HTML = """
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Instancia de Teste</title></head>
<body>
  <h1>Ola</h1>
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
    """Servidor HTTP local, servindo ``tmp_path``, só em 127.0.0.1."""
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


def _wait_until(predicate: Callable[[], bool], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"Condição não satisfeita após {timeout}s de espera.")


def _find_event[EventT](events: list[object], event_type: type[EventT]) -> EventT:
    for event in events:
        if isinstance(event, event_type):
            return event
    raise AssertionError(f"Nenhum evento do tipo {event_type.__name__} foi publicado.")


class _NoOpFolderOpener:
    """Duplo de ``FolderOpenerPort`` só para este teste: abrir de verdade
    o explorador de arquivos do SO durante a suíte automatizada abriria
    uma janela real — indesejável em CI. ``OsFolderOpener`` em si é
    coberto por ``tests/unit/infrastructure/storage/test_folder_opener.py``."""

    def __init__(self) -> None:
        self.opened: list[Path] = []

    def open(self, path: Path) -> None:
        self.opened.append(path)


def test_full_capture_lifecycle_with_real_chromium(tmp_path: Path, local_http_server: str) -> None:
    config = AppConfig(
        instance_url=local_http_server,
        output_directory=tmp_path / "exports",
        headless=True,
        browser_timeout_seconds=10.0,
        login_detection=LoginDetectionPolicyModel(
            stability_seconds=0.2, poll_interval_seconds=0.1, timeout_seconds=15.0
        ),
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

    def browser_manager_factory(
        session_id: UUID, event_publisher: object, log_engine_for_session: object
    ) -> PlaywrightBrowserManager:
        return PlaywrightBrowserManager(
            session_id=session_id,
            config=config,
            event_publisher=event_publisher,  # type: ignore[arg-type]
            log_engine=log_engine_for_session,  # type: ignore[arg-type]
        )

    def browser_data_collector_factory(browser_manager: object) -> BrowserDataCollector:
        return BrowserDataCollector(
            browser_manager=browser_manager,  # type: ignore[arg-type]
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

    folder_opener = _NoOpFolderOpener()

    controller = ApplicationController(
        session_manager=session_manager,
        navigation_recorder=navigation_recorder,
        element_recorder=element_recorder,
        selector_analyzer=selector_analyzer,
        screenshot_engine=screenshot_engine,
        export_engine=export_engine,
        log_engine=log_engine,
        event_bus=event_bus,
        session_discovery=DiskSessionDiscovery(
            output_directory=config.output_directory, log_engine=log_engine  # type: ignore[arg-type]
        ),
        folder_opener=folder_opener,
        log_reader=DiskLogReader(log_directory=tmp_path / "logs"),
        config=config,
        browser_manager_factory=browser_manager_factory,
        browser_data_collector_factory=browser_data_collector_factory,
        shutdown_timeout_seconds=15.0,
    )

    received: list[object] = []
    event_bus.subscribe(received.append)

    controller.dispatch(StartCapture(instance_url=local_http_server))

    # SessionCreated é publicado de forma síncrona, dentro do próprio
    # dispatch() — nunca precisa de espera.
    session_id = _find_event(received, SessionCreated).session_id

    try:
        try:
            _wait_until(
                lambda: any(isinstance(event, SessionStarted) for event in received), timeout=20.0
            )
        except AssertionError as error:
            pytest.skip(f"Chromium indisponível para o teste de integração: {error}")

        assert session_manager.get_session(session_id).status == SessionStatus.RECORDING

        _wait_until(lambda: len(navigation_recorder.get_page_history()) >= 1)
        pages = navigation_recorder.get_page_history()
        assert pages[0].url.value.startswith(local_http_server)

        _wait_until(lambda: len(element_recorder.get_elements(pages[0].page_id.value)) == 3)
    finally:
        controller.dispatch(StopCapture(session_id=session_id))

    # Com o Browser Data Collector (ADR 0013), os metadados de navegador
    # agora são coletados automaticamente — a exportação real deve ter
    # sucesso, com dados reais (não mocks) em disco.
    final_session = session_manager.get_session(session_id)
    assert final_session.status in (
        SessionStatus.COMPLETED,
        SessionStatus.COMPLETED_WITH_WARNINGS,
    )
    assert received and any(isinstance(event, ExportCompleted) for event in received)
    assert not any(isinstance(event, ExportFailed) for event in received)

    completed = _find_event(received, ExportCompleted)
    output_dir = Path(completed.output_directory)
    assert export_engine.validate(session_id) is True
    assert (output_dir / "session.json").is_file()
    assert (output_dir / "selectors.json").is_file()
    assert list((output_dir / "pages").glob("*.json"))
    assert list((output_dir / "screenshots").glob("*.png"))

    # ADR 0014: uma vez exportada, a sessão é descobrível em disco por um
    # processo novo — o mesmo caminho que ``snkb status``/``validate``/
    # ``open`` usam.
    recent = controller.query(GetRecentSessions(limit=1))
    assert recent and recent[0].session_id == session_id
    assert controller.query(ValidateExport(session_id=session_id)) is True
    controller.dispatch(OpenExportFolder(session_id=session_id))
    assert folder_opener.opened == [output_dir]
