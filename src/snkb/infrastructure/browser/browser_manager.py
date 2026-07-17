"""Implementação concreta de ``BrowserManagerPort`` sobre o Playwright
(Module Specifications, Capítulo 3).

Único módulo autorizado a importar ``playwright`` (PW-001). Nunca
preenche formulários, nunca clica em elementos, nunca automatiza a
autenticação Microsoft (RS-001, PW-008) e nunca persiste um objeto
``Page``/``BrowserContext`` fora desta classe (PW-006). Uma instância é
criada por sessão de gravação (RN-005: "Cada gravação criará um
diretório exclusivo"; aqui, um contexto de navegador exclusivo).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import UUID

from playwright.async_api import Browser, BrowserContext, Frame, Page, Playwright, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from snkb.domain.events.base import DomainEvent
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
    BrowserTimeoutError,
    InvalidUrlError,
    PageUnavailableError,
)
from snkb.infrastructure.browser.login_detector import LoginDetector
from snkb.infrastructure.browser.tab_tracker import TabTracker

if TYPE_CHECKING:
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.shared.dtos.app_config import AppConfig

_MILLISECONDS_PER_SECOND = 1000


async def _start_playwright() -> Playwright:
    return await async_playwright().start()


class PlaywrightBrowserManager:
    """Controla o ciclo de vida de um navegador Chromium para uma única
    sessão de gravação."""

    def __init__(
        self,
        session_id: UUID,
        config: AppConfig,
        event_publisher: EventPublisherPort,
        log_engine: LogEnginePort,
        start_playwright: Callable[[], Awaitable[Playwright]] = _start_playwright,
        login_detector: LoginDetector | None = None,
    ) -> None:
        # COD-007: o construtor não inicia o navegador nem faz I/O.
        self._session_id = session_id
        self._config = config
        self._event_publisher = event_publisher
        self._log = log_engine
        self._start_playwright = start_playwright

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._main_page: Page | None = None
        self._closing = False

        self._tab_tracker = TabTracker()
        self._login_detector = login_detector or LoginDetector(
            config.login_detection, config.instance_url
        )

    # ------------------------------------------------------------------
    # BrowserManagerPort
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Inicia Playwright, o navegador, o contexto e a aba principal
        (3.7, Etapas 1-5)."""
        if self._browser is not None:
            raise BrowserInitializationError(
                "O Browser Manager já foi inicializado para esta sessão."
            )

        try:
            self._playwright = await self._start_playwright()
            self._browser = await self._playwright.chromium.launch(headless=self._config.headless)
            self._browser.on("disconnected", self._on_browser_disconnected)

            self._context = await self._browser.new_context(
                viewport={
                    "width": self._config.resolution_width,
                    "height": self._config.resolution_height,
                },
                user_agent=self._config.user_agent,
                accept_downloads=self._config.downloads_enabled,
            )
            self._context.set_default_timeout(
                self._config.browser_timeout_seconds * _MILLISECONDS_PER_SECOND
            )
            self._context.on("page", self._on_new_page)

            self._main_page = await self._context.new_page()
            self._register_page(self._main_page)
        except Exception as error:
            await self.close()
            raise BrowserInitializationError(
                f"Falha ao inicializar o navegador: {error}"
            ) from error

        self._publish(BrowserStarted(session_id=self._session_id))
        self._log.info("Navegador iniciado.", session_id=str(self._session_id))

    async def shutdown(self) -> None:
        """Encerramento normal, solicitado pelo Application Controller
        (RF-007). Publica ``BrowserStopped``."""
        await self.close()
        self._publish(BrowserStopped(session_id=self._session_id))
        self._log.info("Navegador encerrado.", session_id=str(self._session_id))

    async def close(self) -> None:
        """Libera todos os recursos do Playwright, mesmo se algum já
        tiver falhado (PW-007)."""
        self._closing = True
        try:
            for release in (self._close_context, self._close_browser, self._stop_playwright):
                try:
                    await release()
                except Exception as error:  # noqa: BLE001 — cleanup deve continuar mesmo assim.
                    self._log.warning(
                        f"Falha ao liberar recurso do navegador: {error}",
                        session_id=str(self._session_id),
                    )
        finally:
            self._main_page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._closing = False

    async def restart(self) -> None:
        """Estratégia de recuperação (3.18): encerra e reinicializa."""
        await self.close()
        await self.initialize()

    async def open_url(self, url: str) -> None:
        page = self._require_page()
        normalized = self._validate_url(url)
        try:
            await page.goto(normalized, wait_until="domcontentloaded")
        except PlaywrightTimeoutError as error:
            self._publish(BrowserTimeout(session_id=self._session_id))
            raise BrowserTimeoutError(f"Tempo esgotado ao abrir {normalized!r}.") from error
        except PlaywrightError as error:
            raise PageUnavailableError(f"Não foi possível abrir {normalized!r}: {error}") from error

    async def wait_login(self) -> None:
        """Aguarda a autenticação Microsoft manual ser concluída (3.8,
        RF-004). Nunca preenche e-mail, senha, MFA ou código SMS —
        apenas observa a página até que os sinais configurados se
        mantenham verdadeiros por ``stability_seconds``."""
        page = self._require_page()
        policy = self._config.login_detection
        loop = asyncio.get_event_loop()
        deadline = loop.time() + policy.timeout_seconds
        stable_since: float | None = None

        while True:
            if loop.time() > deadline:
                self._publish(BrowserTimeout(session_id=self._session_id))
                raise BrowserTimeoutError(
                    "Tempo esgotado aguardando o login manual do usuário no navegador."
                )

            authenticated = await self._login_detector.is_authenticated(page)
            now = loop.time()

            if authenticated:
                stable_since = stable_since if stable_since is not None else now
                if now - stable_since >= policy.stability_seconds:
                    self._publish(LoginDetected(session_id=self._session_id))
                    self._log.info("Login detectado.", session_id=str(self._session_id))
                    return
            else:
                stable_since = None

            await asyncio.sleep(policy.poll_interval_seconds)

    def current_page(self) -> object:
        return self._main_page

    def current_context(self) -> object:
        return self._context

    def browser_status(self) -> str:
        if self._browser is None:
            return "not_initialized"
        if not self._browser.is_connected():
            return "closed"
        return "running"

    def current_tabs(self) -> list[object]:
        tabs: list[object] = list(self._tab_tracker.open_tabs())
        return tabs

    def is_alive(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_page(self) -> Page:
        if self._main_page is None:
            raise PageUnavailableError(
                "Nenhuma página ativa: chame initialize() antes desta operação."
            )
        return self._main_page

    @staticmethod
    def _validate_url(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise InvalidUrlError(f"URL inválida para navegação: {url!r}")
        return url

    def _register_page(self, page: Page) -> str:
        tab_id = self._tab_tracker.register(page)
        page.on("close", lambda _closed_page: self._on_page_closed(page))
        page.on("framenavigated", lambda frame: self._on_frame_navigated(page, frame))
        return tab_id

    def _on_new_page(self, page: Page) -> None:
        # A aba principal já foi registrada explicitamente em
        # initialize(); este handler cobre apenas abas realmente novas
        # (ex.: links com target="_blank", window.open()).
        if self._tab_tracker.is_tracked(page):
            return
        tab_id = self._register_page(page)
        self._publish(TabCreated(session_id=self._session_id, tab_id=tab_id))

    def _on_page_closed(self, page: Page) -> None:
        tab_id = self._tab_tracker.close(page)
        if tab_id is not None:
            self._publish(TabClosed(session_id=self._session_id, tab_id=tab_id))

    def _on_frame_navigated(self, page: Page, frame: Frame) -> None:
        # RF-009 (associar elementos a frames) é responsabilidade do
        # Element Recorder; aqui só rastreamos a navegação do frame
        # principal de cada aba (RF-008, 3.10).
        if frame != page.main_frame:
            return
        tab_id = self._tab_tracker.tab_id_for(page) or ""
        self._publish(UrlChanged(session_id=self._session_id, url=frame.url, tab_id=tab_id))
        self._publish(PageChanged(session_id=self._session_id, url=frame.url, tab_id=tab_id))

    def _on_browser_disconnected(self, _browser: Browser) -> None:
        if self._closing:
            return  # Desconexão esperada, causada pelo nosso próprio close().
        self._publish(
            BrowserCrashed(
                session_id=self._session_id,
                reason="O navegador foi encerrado inesperadamente.",
            )
        )
        self._log.error("Navegador encerrado inesperadamente.", session_id=str(self._session_id))

    async def _close_context(self) -> None:
        if self._context is not None:
            await self._context.close()

    async def _close_browser(self) -> None:
        if self._browser is not None:
            await self._browser.close()

    async def _stop_playwright(self) -> None:
        if self._playwright is not None:
            await self._playwright.stop()

    def _publish(self, event: DomainEvent) -> None:
        self._event_publisher.publish(event)
