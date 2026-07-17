"""Teste de integração real do Browser Manager: abre um Chromium de
verdade (headless) e percorre o ciclo de vida completo contra um
servidor HTTP local (sem acessar a internet ou uma instância real do
ServiceNow — AI Coding Standards, seção 19).

Requer ``playwright install chromium``. Se os binários do navegador
não estiverem instalados, o teste é pulado em vez de falhar — a lógica
de orquestração já é coberta pelos duplos de teste em
``tests/unit/infrastructure/browser/test_browser_manager.py``.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator, Iterator
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.async_api import Page

from snkb.domain.events.browser_events import (
    BrowserStarted,
    BrowserStopped,
    PageChanged,
    UrlChanged,
)
from snkb.infrastructure.browser.browser_manager import PlaywrightBrowserManager
from snkb.shared.dtos.app_config import AppConfig


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


@pytest.fixture
def local_http_server(tmp_path: Path) -> Iterator[str]:
    """Servidor HTTP local, servindo ``tmp_path``, só em 127.0.0.1."""
    (tmp_path / "test.html").write_text(
        "<title>Pagina de Teste</title><h1>Ola</h1>", encoding="utf-8"
    )
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
async def browser_manager(
    tmp_path: Path,
) -> AsyncIterator[tuple[PlaywrightBrowserManager, _RecordingEventPublisher]]:
    config = AppConfig(
        instance_url="https://empresa.service-now.com",
        output_directory=tmp_path,
        headless=True,
    )
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()
    manager = PlaywrightBrowserManager(
        session_id=uuid4(),
        config=config,
        event_publisher=publisher,
        log_engine=log,
    )
    try:
        await manager.initialize()
    except Exception as error:  # noqa: BLE001 — ambiente sem Chromium instalado.
        pytest.skip(f"Chromium indisponível para o teste de integração: {error}")
    yield manager, publisher
    await manager.close()


async def test_full_lifecycle_with_real_chromium(
    browser_manager: tuple[PlaywrightBrowserManager, _RecordingEventPublisher],
    local_http_server: str,
) -> None:
    manager, publisher = browser_manager

    assert manager.browser_status() == "running"
    assert len(publisher.of_type(BrowserStarted)) == 1

    await manager.open_url(f"{local_http_server}/test.html")

    page = manager.current_page()
    assert isinstance(page, Page)
    assert await page.title() == "Pagina de Teste"
    assert len(publisher.of_type(PageChanged)) >= 1
    assert len(publisher.of_type(UrlChanged)) >= 1

    await manager.shutdown()

    assert manager.browser_status() == "not_initialized"
    assert manager.is_alive() is False
    assert len(publisher.of_type(BrowserStopped)) == 1
