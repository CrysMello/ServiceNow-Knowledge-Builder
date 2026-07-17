"""Testes do ``PlaywrightBrowserManager`` usando duplos de teste para
Playwright — nenhum destes testes abre um navegador real (isso fica a
cargo de ``tests/integration/test_browser_manager_integration.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from snkb.domain.events.browser_events import (
    BrowserCrashed,
    BrowserStarted,
    BrowserStopped,
    BrowserTimeout,
    LoginDetected,
    PageChanged,
    TabClosed,
    TabCreated,
    UrlChanged,
)
from snkb.domain.exceptions.browser_exceptions import (
    BrowserInitializationError,
    InvalidUrlError,
    PageUnavailableError,
)
from snkb.domain.exceptions.browser_exceptions import (
    BrowserTimeoutError as SnkbBrowserTimeoutError,
)
from snkb.infrastructure.browser.browser_manager import PlaywrightBrowserManager
from snkb.shared.dtos.app_config import AppConfig, LoginDetectionPolicyModel

_SESSION_ID = UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")
_INSTANCE_URL = "https://empresa.service-now.com"


# ----------------------------------------------------------------------
# Duplos de teste para a árvore de objetos do Playwright
# ----------------------------------------------------------------------


class _EventEmitter:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., object]]] = {}

    def on(self, event: str, handler: Callable[..., object]) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, *args: object) -> None:
        for handler in list(self._handlers.get(event, [])):
            handler(*args)


class _FakeFrame:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakePage(_EventEmitter):
    def __init__(self, url: str = "about:blank") -> None:
        super().__init__()
        self.url = url
        self._closed = False
        self.main_frame = _FakeFrame(url)
        self.goto_calls: list[str] = []
        self.goto_error: Exception | None = None

    def is_closed(self) -> bool:
        return self._closed

    async def title(self) -> str:
        return ""

    def locator(self, _selector: str) -> object:
        raise NotImplementedError("não exercitado nestes testes")

    async def goto(self, url: str, wait_until: str = "load") -> None:
        del wait_until
        self.goto_calls.append(url)
        if self.goto_error is not None:
            raise self.goto_error

    def simulate_navigation(self, url: str) -> None:
        self.url = url
        self.main_frame = _FakeFrame(url)
        self.emit("framenavigated", self.main_frame)

    def simulate_close(self) -> None:
        self._closed = True
        self.emit("close", self)


class _FakeBrowserContext(_EventEmitter):
    def __init__(self) -> None:
        super().__init__()
        self.default_timeout_ms: float | None = None
        self.closed = False
        self.close_error: Exception | None = None
        self.pages_created: list[_FakePage] = []

    def set_default_timeout(self, ms: float) -> None:
        self.default_timeout_ms = ms

    async def new_page(self) -> _FakePage:
        page = _FakePage()
        self.pages_created.append(page)
        return page

    async def close(self) -> None:
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class _FakeBrowser(_EventEmitter):
    def __init__(self) -> None:
        super().__init__()
        self._connected = True
        self.new_context_kwargs: list[dict[str, object]] = []

    def is_connected(self) -> bool:
        return self._connected

    async def new_context(self, **kwargs: object) -> _FakeBrowserContext:
        self.new_context_kwargs.append(kwargs)
        return _FakeBrowserContext()

    async def close(self) -> None:
        self._connected = False
        self.emit("disconnected", self)

    def simulate_disconnect(self) -> None:
        self._connected = False
        self.emit("disconnected", self)


class _FakeChromium:
    def __init__(
        self, browser: _FakeBrowser | None = None, launch_error: Exception | None = None
    ) -> None:
        # Se um `browser` específico for passado, `launch()` sempre o
        # devolve (útil quando o teste precisa manipular essa mesma
        # instância depois). Caso contrário, cada chamada a `launch()`
        # cria um `_FakeBrowser` novo e conectado — assim como o
        # Playwright real cria um processo novo a cada lançamento,
        # o que importa para testes que chamam initialize() mais de
        # uma vez (ex.: via restart()).
        self._fixed_browser = browser
        self.launch_error = launch_error
        self.launch_kwargs: list[dict[str, object]] = []
        self.launched_browsers: list[_FakeBrowser] = []

    @property
    def browser(self) -> _FakeBrowser:
        return self.launched_browsers[-1]

    async def launch(self, **kwargs: object) -> _FakeBrowser:
        self.launch_kwargs.append(kwargs)
        if self.launch_error is not None:
            raise self.launch_error
        browser = self._fixed_browser if self._fixed_browser is not None else _FakeBrowser()
        self.launched_browsers.append(browser)
        return browser


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium | None = None) -> None:
        self.chromium = chromium or _FakeChromium()
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


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


class _FakeLoginDetector:
    def __init__(self, results: list[bool]) -> None:
        self._results = results
        self.calls = 0

    async def is_authenticated(self, page: object) -> bool:
        del page
        index = min(self.calls, len(self._results) - 1)
        self.calls += 1
        return self._results[index]


def _make_config(**overrides: object) -> AppConfig:
    defaults: dict[str, object] = {
        "instance_url": _INSTANCE_URL,
        "output_directory": Path("exports"),
        "headless": True,
        "browser_timeout_seconds": 5.0,
    }
    defaults.update(overrides)
    return AppConfig(**defaults)  # type: ignore[arg-type]


def _make_manager(
    chromium: _FakeChromium | None = None,
    login_detector: object = None,
    config: AppConfig | None = None,
) -> tuple[PlaywrightBrowserManager, _FakeChromium, _RecordingEventPublisher, _RecordingLogEngine]:
    fake_chromium = chromium or _FakeChromium()
    fake_playwright = _FakePlaywright(chromium=fake_chromium)
    publisher = _RecordingEventPublisher()
    log = _RecordingLogEngine()

    async def start_playwright() -> _FakePlaywright:
        return fake_playwright

    manager = PlaywrightBrowserManager(
        session_id=_SESSION_ID,
        config=config or _make_config(),
        event_publisher=publisher,
        log_engine=log,
        start_playwright=start_playwright,  # type: ignore[arg-type]
        login_detector=login_detector,  # type: ignore[arg-type]
    )
    return manager, fake_chromium, publisher, log


# ----------------------------------------------------------------------
# initialize()
# ----------------------------------------------------------------------


async def test_initialize_happy_path_publishes_browser_started() -> None:
    manager, chromium, publisher, _log = _make_manager()

    await manager.initialize()

    assert chromium.launch_kwargs[0]["headless"] is True
    assert len(publisher.of_type(BrowserStarted)) == 1
    assert manager.browser_status() == "running"
    assert manager.is_alive() is True
    assert manager.current_page() is not None


async def test_initialize_sets_context_default_timeout_from_config() -> None:
    manager, chromium, _publisher, _log = _make_manager(
        config=_make_config(browser_timeout_seconds=12.5)
    )
    await manager.initialize()

    assert chromium.browser.new_context_kwargs  # new_context foi chamado
    context = manager.current_context()
    assert isinstance(context, _FakeBrowserContext)
    assert context.default_timeout_ms == 12_500.0


async def test_initialize_twice_raises_browser_initialization_error() -> None:
    manager, _chromium, _publisher, _log = _make_manager()
    await manager.initialize()

    with pytest.raises(BrowserInitializationError):
        await manager.initialize()


async def test_initialize_failure_cleans_up_and_raises() -> None:
    chromium = _FakeChromium(launch_error=RuntimeError("boom"))
    manager, _chromium, publisher, _log = _make_manager(chromium=chromium)

    with pytest.raises(BrowserInitializationError):
        await manager.initialize()

    assert publisher.of_type(BrowserStarted) == []
    assert manager.browser_status() == "not_initialized"


# ----------------------------------------------------------------------
# open_url()
# ----------------------------------------------------------------------


async def test_open_url_before_initialize_raises_page_unavailable() -> None:
    manager, _chromium, _publisher, _log = _make_manager()

    with pytest.raises(PageUnavailableError):
        await manager.open_url(_INSTANCE_URL)


async def test_open_url_rejects_invalid_url_without_navigating() -> None:
    manager, _chromium, _publisher, _log = _make_manager()
    await manager.initialize()
    page = manager.current_page()
    assert isinstance(page, _FakePage)

    with pytest.raises(InvalidUrlError):
        await manager.open_url("not-a-url")

    assert page.goto_calls == []


async def test_open_url_calls_goto_with_the_given_url() -> None:
    manager, chromium, _publisher, _log = _make_manager()
    await manager.initialize()

    await manager.open_url(_INSTANCE_URL)

    page = manager.current_page()
    assert isinstance(page, _FakePage)
    assert page.goto_calls == [_INSTANCE_URL]


async def test_open_url_timeout_publishes_browser_timeout_and_raises() -> None:
    manager, _chromium, publisher, _log = _make_manager()
    await manager.initialize()
    page = manager.current_page()
    assert isinstance(page, _FakePage)
    page.goto_error = PlaywrightTimeoutError("timeout")

    with pytest.raises(SnkbBrowserTimeoutError):
        await manager.open_url(_INSTANCE_URL)

    assert len(publisher.of_type(BrowserTimeout)) == 1


async def test_open_url_generic_playwright_error_raises_page_unavailable() -> None:
    manager, _chromium, _publisher, _log = _make_manager()
    await manager.initialize()
    page = manager.current_page()
    assert isinstance(page, _FakePage)
    page.goto_error = PlaywrightError("boom")

    with pytest.raises(PageUnavailableError):
        await manager.open_url(_INSTANCE_URL)


# ----------------------------------------------------------------------
# wait_login()
# ----------------------------------------------------------------------


async def test_wait_login_publishes_login_detected_once_stable() -> None:
    policy = LoginDetectionPolicyModel(
        stability_seconds=0.03, poll_interval_seconds=0.01, timeout_seconds=2.0
    )
    detector = _FakeLoginDetector(results=[True])
    manager, _chromium, publisher, _log = _make_manager(
        login_detector=detector,
        config=_make_config(login_detection=policy),
    )
    await manager.initialize()

    await manager.wait_login()

    assert len(publisher.of_type(LoginDetected)) == 1


async def test_wait_login_times_out_if_never_authenticated() -> None:
    policy = LoginDetectionPolicyModel(
        stability_seconds=0.02, poll_interval_seconds=0.01, timeout_seconds=0.05
    )
    detector = _FakeLoginDetector(results=[False])
    manager, _chromium, publisher, _log = _make_manager(
        login_detector=detector,
        config=_make_config(login_detection=policy),
    )
    await manager.initialize()

    with pytest.raises(SnkbBrowserTimeoutError):
        await manager.wait_login()

    assert len(publisher.of_type(BrowserTimeout)) == 1


async def test_wait_login_before_initialize_raises_page_unavailable() -> None:
    manager, _chromium, _publisher, _log = _make_manager()

    with pytest.raises(PageUnavailableError):
        await manager.wait_login()


# ----------------------------------------------------------------------
# shutdown() / close() / restart()
# ----------------------------------------------------------------------


async def test_shutdown_closes_everything_and_publishes_browser_stopped() -> None:
    chromium = _FakeChromium()
    manager, _chromium, publisher, _log = _make_manager(chromium=chromium)
    await manager.initialize()

    await manager.shutdown()

    assert chromium.browser.is_connected() is False
    assert manager.browser_status() == "not_initialized"
    assert len(publisher.of_type(BrowserStopped)) == 1


async def test_close_tolerates_individual_resource_failures() -> None:
    browser = _FakeBrowser()
    chromium = _FakeChromium(browser=browser)
    manager, _chromium, _publisher, log = _make_manager(chromium=chromium)
    await manager.initialize()

    context = manager.current_context()
    assert isinstance(context, _FakeBrowserContext)
    context.close_error = RuntimeError("falha ao fechar o contexto")

    await manager.close()

    # Mesmo com a falha no contexto, o navegador e o Playwright ainda
    # devem ter sido liberados (PW-007).
    assert browser.is_connected() is False
    assert any("falha ao fechar o contexto" in message for message in log.messages)


async def test_restart_reinitializes_after_closing() -> None:
    manager, _chromium, publisher, _log = _make_manager()
    await manager.initialize()

    await manager.restart()

    assert len(publisher.of_type(BrowserStarted)) == 2
    assert manager.browser_status() == "running"


# ----------------------------------------------------------------------
# Rastreamento de abas e navegação
# ----------------------------------------------------------------------


async def test_main_page_navigation_publishes_url_and_page_changed_with_tab_id() -> None:
    manager, _chromium, publisher, _log = _make_manager()
    await manager.initialize()
    page = manager.current_page()
    assert isinstance(page, _FakePage)

    page.simulate_navigation("https://empresa.service-now.com/list")

    url_changed = publisher.of_type(UrlChanged)
    page_changed = publisher.of_type(PageChanged)
    assert len(url_changed) == 1
    assert len(page_changed) == 1
    assert url_changed[0].url == "https://empresa.service-now.com/list"  # type: ignore[attr-defined]
    assert url_changed[0].tab_id == page_changed[0].tab_id  # type: ignore[attr-defined]
    assert url_changed[0].tab_id != ""  # type: ignore[attr-defined]


async def test_new_tab_via_context_event_publishes_tab_created() -> None:
    browser = _FakeBrowser()
    chromium = _FakeChromium(browser=browser)
    manager, _chromium, publisher, _log = _make_manager(chromium=chromium)
    await manager.initialize()

    context = manager.current_context()
    assert isinstance(context, _FakeBrowserContext)
    new_page = _FakePage(url="about:blank")
    context.emit("page", new_page)

    assert len(publisher.of_type(TabCreated)) == 1
    assert len(manager.current_tabs()) == 2  # aba principal + a nova


async def test_page_close_publishes_tab_closed_and_removes_from_open_tabs() -> None:
    browser = _FakeBrowser()
    chromium = _FakeChromium(browser=browser)
    manager, _chromium, publisher, _log = _make_manager(chromium=chromium)
    await manager.initialize()

    context = manager.current_context()
    assert isinstance(context, _FakeBrowserContext)
    new_page = _FakePage(url="about:blank")
    context.emit("page", new_page)

    new_page.simulate_close()

    assert len(publisher.of_type(TabClosed)) == 1
    assert len(manager.current_tabs()) == 1  # só a aba principal permanece


async def test_context_page_event_for_the_main_page_does_not_duplicate_tab_created() -> None:
    manager, _chromium, publisher, _log = _make_manager()
    await manager.initialize()

    context = manager.current_context()
    assert isinstance(context, _FakeBrowserContext)
    main_page = manager.current_page()
    # simula o evento "page" disparando também para a própria aba principal
    context.emit("page", main_page)

    assert publisher.of_type(TabCreated) == []


# ----------------------------------------------------------------------
# Encerramento inesperado do navegador
# ----------------------------------------------------------------------


async def test_unexpected_disconnect_publishes_browser_crashed() -> None:
    browser = _FakeBrowser()
    chromium = _FakeChromium(browser=browser)
    manager, _chromium, publisher, _log = _make_manager(chromium=chromium)
    await manager.initialize()

    browser.simulate_disconnect()

    assert len(publisher.of_type(BrowserCrashed)) == 1


async def test_disconnect_during_our_own_shutdown_does_not_publish_browser_crashed() -> None:
    browser = _FakeBrowser()
    chromium = _FakeChromium(browser=browser)
    manager, _chromium, publisher, _log = _make_manager(chromium=chromium)
    await manager.initialize()

    await manager.shutdown()

    assert publisher.of_type(BrowserCrashed) == []
