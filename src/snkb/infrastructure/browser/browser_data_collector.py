"""Implementação concreta de ``BrowserDataCollectorPort`` — a ponte
entre o Playwright real e Element Recorder, Selector Analyzer e
Screenshot Engine (ADR 0013).

Único outro módulo, além de ``browser_manager.py``, autorizado a
importar ``playwright`` (PW-001): o objeto opaco devolvido por
``BrowserManagerPort.current_page()`` só é tratado como
``playwright.async_api.Page`` aqui, nunca na camada de aplicação.
Nunca lê nem armazena o valor de um campo — mesma regra do Element
Recorder (RS-002, ADR 0007), aplicada na origem da coleta.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import platform
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Frame, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from snkb.application.ports.browser_data_collector_port import PageCaptureResult
from snkb.domain.enums.screenshot_type import ScreenshotType
from snkb.domain.events.browser_events import PageChanged
from snkb.domain.events.system_events import ErrorOccurred
from snkb.domain.exceptions.collector_exceptions import CollectorNotActiveError
from snkb.domain.value_objects.viewport import Resolution, Viewport
from snkb.modules.elements.element_recorder import RawElementObservation
from snkb.modules.screenshots.screenshot_engine import RawScreenshotObservation

if TYPE_CHECKING:
    from collections.abc import Callable

    from snkb.application.ports.browser_manager_port import BrowserManagerPort
    from snkb.application.ports.element_recorder_port import ElementRecorderPort
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.application.ports.navigation_recorder_port import NavigationRecorderPort
    from snkb.application.ports.screenshot_engine_port import ScreenshotEnginePort
    from snkb.application.ports.selector_analyzer_port import SelectorAnalyzerPort
    from snkb.application.ports.session_manager_port import SessionManagerPort
    from snkb.domain.events.base import DomainEvent
    from snkb.shared.dtos.app_config import AppConfig

    class _NavigationRecorderForCollector(NavigationRecorderPort, Protocol):
        def observe_navigation(self, tab_id: str, url: str, title: str | None = None) -> None: ...
        def get_tab_id_for_page(self, page_id: UUID) -> str | None: ...

    class _ElementRecorderForCollector(ElementRecorderPort, Protocol):
        def observe_elements(
            self, session_id: UUID, page_id: UUID, elements: list[RawElementObservation]
        ) -> None: ...

    class _SelectorAnalyzerForCollector(SelectorAnalyzerPort, Protocol):
        def register_session_for_page(self, session_id: UUID, page_id: UUID) -> None: ...

    class _ScreenshotEngineForCollector(ScreenshotEnginePort, Protocol):
        def stage_capture(
            self,
            session_id: UUID,
            page_id: UUID,
            capture_type: ScreenshotType,
            observation: RawScreenshotObservation,
        ) -> None: ...

    class _SubscribableEventBus(EventPublisherPort, Protocol):
        def subscribe(self, handler: Callable[[DomainEvent], None]) -> None: ...

    class _ScreenshotByteSink(Protocol):
        def put(self, screenshot_id: UUID, data: bytes) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


# JS único, avaliado uma vez por frame (principal + cada frame acessível).
# Nunca lê ``value``/conteúdo de campos de formulário — só metadados
# estruturais (RS-002, ADR 0007). ``data-testid`` é lido no DOM, mas
# descartado no lado Python: ``RawElementObservation``/``Element`` não
# têm esse campo ainda (limitação já documentada na ADR 0008).
_DOM_EXTRACTION_SCRIPT = """
(maxElements) => {
    function isVisible(el) {
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
        }
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    function computeAccessibleName(el) {
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) return ariaLabel.trim();
        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const text = labelledBy.split(/\\s+/).map((id) => {
                const ref = document.getElementById(id);
                return ref ? ref.textContent : '';
            }).join(' ').trim();
            if (text) return text;
        }
        const text = (el.innerText || el.textContent || '').trim();
        return text.slice(0, 120);
    }

    function computeLabel(el) {
        if (el.id) {
            const label = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
            if (label) return (label.innerText || label.textContent || '').trim().slice(0, 120);
        }
        const parentLabel = el.closest('label');
        if (parentLabel) {
            return (parentLabel.innerText || parentLabel.textContent || '').trim().slice(0, 120);
        }
        return null;
    }

    function isSensitiveHint(el) {
        const haystack = [
            el.id || '', el.getAttribute('name') || '', el.getAttribute('autocomplete') || ''
        ].join(' ').toLowerCase();
        return /password|senha|cpf|ssn|secret|token|credit|cartao/.test(haystack);
    }

    const selector = 'button, input, select, textarea, a, [role], [aria-label],' +
        ' [data-testid], [onclick], [tabindex]';
    const nodeList = Array.from(document.querySelectorAll(selector)).slice(0, maxElements);
    const indexOf = new Map();
    nodeList.forEach((el, i) => indexOf.set(el, i));

    return nodeList.map((el) => {
        let parentIndex = null;
        let ancestor = el.parentElement;
        while (ancestor) {
            if (indexOf.has(ancestor)) { parentIndex = indexOf.get(ancestor); break; }
            ancestor = ancestor.parentElement;
        }
        const tag = el.tagName.toLowerCase();
        return {
            tag: tag,
            role: el.getAttribute('role'),
            inputType: tag === 'input' ? (el.getAttribute('type') || 'text') : null,
            accessibleName: computeAccessibleName(el),
            label: computeLabel(el),
            placeholder: el.getAttribute('placeholder'),
            htmlId: el.id || null,
            name: el.getAttribute('name'),
            classes: (typeof el.className === 'string' ? el.className : '')
                .split(/\\s+/).filter(Boolean).slice(0, 10),
            required: el.required === true || el.getAttribute('aria-required') === 'true',
            readonly: el.readOnly === true || el.getAttribute('aria-readonly') === 'true',
            disabled: el.disabled === true || el.getAttribute('aria-disabled') === 'true',
            visible: isVisible(el),
            isSensitiveHint: isSensitiveHint(el),
            parentIndex: parentIndex,
        };
    });
}
"""


class BrowserDataCollector:
    """Observa a página real de uma sessão e alimenta Element Recorder,
    Selector Analyzer e Screenshot Engine com dados reais, associados
    à página que o Navigation Recorder já rastreia."""

    def __init__(
        self,
        browser_manager: BrowserManagerPort,
        navigation_recorder: _NavigationRecorderForCollector,
        element_recorder: _ElementRecorderForCollector,
        selector_analyzer: _SelectorAnalyzerForCollector,
        screenshot_engine: _ScreenshotEngineForCollector,
        session_manager: SessionManagerPort,
        event_bus: _SubscribableEventBus,
        log_engine: LogEnginePort,
        screenshot_store: _ScreenshotByteSink,
        config: AppConfig,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._browser_manager = browser_manager
        self._navigation_recorder = navigation_recorder
        self._element_recorder = element_recorder
        self._selector_analyzer = selector_analyzer
        self._screenshot_engine = screenshot_engine
        self._session_manager = session_manager
        self._event_bus = event_bus
        self._log = log_engine
        self._screenshot_store = screenshot_store
        self._config = config
        self._now = now

        self._active = False
        self._session_id: UUID | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending_tasks: dict[str, asyncio.Task[None]] = {}
        self._pending_since: dict[str, float] = {}
        self._last_signature: dict[UUID, str] = {}
        self._known_element_count: dict[UUID, int] = {}

    # ------------------------------------------------------------------
    # BrowserDataCollectorPort
    # ------------------------------------------------------------------

    async def start(self, session_id: UUID) -> None:
        if self._active:
            return  # idempotente — mesma sessão já iniciada.

        self._session_id = session_id
        self._active = True
        self._loop = asyncio.get_running_loop()
        self._event_bus.subscribe(self._on_domain_event)

        with contextlib.suppress(Exception):
            await self._collect_session_metadata(session_id)

        self._log.info("Browser Data Collector iniciado.", session_id=str(session_id))

    async def capture_current_page(self) -> PageCaptureResult | None:
        session_id = self._require_active()
        page = self._current_page()
        if page is None or page.is_closed():
            return None

        nav_page = self._navigation_recorder.get_current_page()
        if nav_page is None:
            self._log.warning(
                "Nenhuma página atual conhecida pelo Navigation Recorder; nada a capturar."
            )
            return None
        page_id = nav_page.page_id.value

        warnings: list[str] = []
        await self._wait_for_dom_content(page, warnings)

        try:
            raw_elements, frame_warnings = await self._collect_elements(page)
        except (PlaywrightError, PlaywrightTimeoutError) as error:
            self._log.exception("Falha ao coletar DOM.", page_id=str(page_id))
            self._event_bus.publish(
                ErrorOccurred(
                    session_id=session_id, module="BrowserDataCollector", message=str(error)
                )
            )
            return None
        warnings.extend(frame_warnings)

        signature = self._compute_signature(nav_page.url.value, raw_elements)
        if not warnings and self._last_signature.get(page_id) == signature:
            return None  # Deduplicação: nada novo desde a última captura bem-sucedida.

        title = await self._safe_title(page, fallback=nav_page.title, warnings=warnings)
        self._maybe_update_page_title(page_id, nav_page.url.value, nav_page.title, title)

        self._element_recorder.observe_elements(session_id, page_id, raw_elements)
        previous_count = self._known_element_count.get(page_id, 0)
        elements = self._element_recorder.capture_elements(page_id)
        new_count = max(len(elements) - previous_count, 0)
        self._known_element_count[page_id] = len(elements)

        self._selector_analyzer.register_session_for_page(session_id, page_id)
        for element in elements:
            try:
                self._selector_analyzer.analyze(element.element_id.value)
            except Exception as error:  # noqa: BLE001 — um elemento ruim não pode travar os demais.
                warnings.append(f"Falha ao gerar seletores para um elemento: {error}")

        screenshot_id: UUID | None = None
        try:
            screenshot_id = await self._capture_screenshot(session_id, page_id, page)
        except Exception as error:  # noqa: BLE001 — screenshot é evidência, não bloqueante.
            warnings.append(f"Falha ao capturar screenshot: {error}")
            self._log.exception("Falha ao capturar screenshot.", page_id=str(page_id))

        self._last_signature[page_id] = signature
        return PageCaptureResult(
            session_id=session_id,
            page_id=page_id,
            url=nav_page.url.value,
            title=title,
            element_count=len(elements),
            new_element_count=new_count,
            screenshot_id=screenshot_id,
            captured_at=self._now(),
            warnings=tuple(warnings),
        )

    async def stop(self) -> None:
        self._require_active()

        pending = [task for task in self._pending_tasks.values() if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._pending_tasks.clear()
        self._pending_since.clear()

        # A captura final roda enquanto o coletor ainda está "ativo"
        # (capture_current_page() exige isso) — só desativa depois,
        # para não descartar silenciosamente o último estado observado.
        with contextlib.suppress(Exception):
            await self.capture_current_page()

        self._active = False
        self._log.info("Browser Data Collector encerrado.", session_id=str(self._session_id))

    # ------------------------------------------------------------------
    # Estabilidade de página (debounce por aba, sem networkidle)
    # ------------------------------------------------------------------

    def _on_domain_event(self, event: DomainEvent) -> None:
        if not self._active or self._session_id is None:
            return
        if isinstance(event, PageChanged) and event.session_id == self._session_id:
            self._schedule_stability_check(event.tab_id)

    def _schedule_stability_check(self, tab_id: str) -> None:
        assert self._loop is not None
        now = self._loop.time()
        self._pending_since.setdefault(tab_id, now)

        existing = self._pending_tasks.get(tab_id)
        if existing is not None and not existing.done():
            existing.cancel()
        self._pending_tasks[tab_id] = self._loop.create_task(self._debounce_and_capture(tab_id))

    async def _debounce_and_capture(self, tab_id: str) -> None:
        assert self._loop is not None
        policy = self._config.capture_policy
        pending_since = self._pending_since.get(tab_id, self._loop.time())
        max_wait_deadline = pending_since + policy.page_stability_max_wait_seconds
        remaining_to_max = max_wait_deadline - self._loop.time()
        wait_seconds = min(policy.page_stability_seconds, max(remaining_to_max, 0.0))

        try:
            await asyncio.sleep(wait_seconds)
        except asyncio.CancelledError:
            return  # Substituída por uma navegação mais recente na mesma aba.

        self._pending_since.pop(tab_id, None)
        try:
            await self.capture_current_page()
        except Exception:  # noqa: BLE001 — nunca deixa uma tarefa em segundo plano matar a sessão.
            self._log.exception("Falha ao capturar página após estabilidade.", tab_id=tab_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_active(self) -> UUID:
        if not self._active or self._session_id is None:
            raise CollectorNotActiveError(
                "O Browser Data Collector não está ativo; chame start() antes."
            )
        return self._session_id

    def _current_page(self) -> Page | None:
        page = self._browser_manager.current_page()
        if page is None:
            return None
        return cast(Page, page)

    async def _collect_session_metadata(self, session_id: UUID) -> None:
        browser_version = "unknown"
        page = self._current_page()
        if page is not None:
            with contextlib.suppress(Exception):
                browser = page.context.browser
                if browser is not None:
                    browser_version = browser.version

        metadata: dict[str, object] = {
            "browser": "Chromium",
            "browser_version": browser_version,
            "operating_system": f"{platform.system()} {platform.release()}".strip(),
            "screen_resolution": Resolution(
                width=self._config.resolution_width, height=self._config.resolution_height
            ),
            "viewport": Viewport(
                width=self._config.resolution_width, height=self._config.resolution_height
            ),
        }
        self._session_manager.update_metadata(session_id, metadata)

    async def _wait_for_dom_content(self, page: Page, warnings: list[str]) -> None:
        timeout_ms = self._config.capture_policy.page_stability_max_wait_seconds * 1000
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            warnings.append(
                "Página não atingiu domcontentloaded dentro do tempo limite; "
                "prosseguindo com o estado atual (captura parcial)."
            )
        except PlaywrightError:
            pass  # Página pode já estar carregada; não é um erro real.

    async def _safe_title(self, page: Page, *, fallback: str, warnings: list[str]) -> str:
        try:
            title = await page.title()
        except (PlaywrightError, PlaywrightTimeoutError):
            warnings.append("Não foi possível obter o título da página; mantido o valor anterior.")
            return fallback
        return title or fallback

    def _maybe_update_page_title(
        self, page_id: UUID, url: str, previous_title: str, new_title: str
    ) -> None:
        if not new_title or new_title == previous_title:
            return
        tab_id = self._navigation_recorder.get_tab_id_for_page(page_id)
        if tab_id is None:
            return
        self._navigation_recorder.observe_navigation(tab_id=tab_id, url=url, title=new_title)
        self._navigation_recorder.update_page(page_id)

    async def _collect_elements(self, page: Page) -> tuple[list[RawElementObservation], list[str]]:
        max_elements = self._config.capture_policy.max_elements_per_page
        observations: list[RawElementObservation] = []
        warnings: list[str] = []

        main_frame = page.main_frame
        observations.extend(await self._evaluate_frame(main_frame, main_frame.url, max_elements))

        for frame in page.frames:
            if frame == main_frame:
                continue
            try:
                observations.extend(await self._evaluate_frame(frame, frame.url, max_elements))
            except (PlaywrightError, PlaywrightTimeoutError) as error:
                warnings.append(f"Frame inacessível ({frame.url or 'desconhecido'}): {error}")
                self._log.warning(f"Frame inacessível: {error}", frame_url=frame.url)

        return observations[:max_elements], warnings

    @staticmethod
    async def _evaluate_frame(
        frame: Frame, origin_url: str, max_elements: int
    ) -> list[RawElementObservation]:
        raw_items = await frame.evaluate(_DOM_EXTRACTION_SCRIPT, max_elements)
        frame_selector = f"iframe[name='{frame.name}']" if frame.name else None

        observations: list[RawElementObservation] = []
        for item in raw_items:
            observations.append(
                RawElementObservation(
                    frame_origin=origin_url,
                    frame_selector=frame_selector,
                    tag=item["tag"],
                    role=item.get("role"),
                    input_type=item.get("inputType"),
                    accessible_name=item.get("accessibleName") or None,
                    label=item.get("label") or None,
                    placeholder=item.get("placeholder") or None,
                    html_id=item.get("htmlId") or None,
                    name=item.get("name") or None,
                    classes=tuple(item.get("classes", [])),
                    required=bool(item.get("required", False)),
                    readonly=bool(item.get("readonly", False)),
                    disabled=bool(item.get("disabled", False)),
                    visible=bool(item.get("visible", True)),
                    enabled=not bool(item.get("disabled", False)),
                    is_sensitive_hint=bool(item.get("isSensitiveHint", False)),
                    parent_index=item.get("parentIndex"),
                )
            )
        return observations

    async def _capture_screenshot(self, session_id: UUID, page_id: UUID, page: Page) -> UUID | None:
        if not self._config.capture_policy.capture_screenshots:
            return None

        full_page = self._config.capture_policy.full_page_screenshots
        capture_type = ScreenshotType.FULL_PAGE if full_page else ScreenshotType.VIEWPORT
        png_bytes = await page.screenshot(type="png", full_page=full_page)

        viewport = page.viewport_size
        width = viewport["width"] if viewport else self._config.resolution_width
        height = viewport["height"] if viewport else self._config.resolution_height

        self._screenshot_engine.stage_capture(
            session_id,
            page_id,
            capture_type,
            RawScreenshotObservation(width=width, height=height, byte_size=len(png_bytes)),
        )
        screenshot = self._screenshot_engine.capture_page(page_id)
        self._screenshot_store.put(screenshot.screenshot_id.value, png_bytes)
        return screenshot.screenshot_id.value

    @staticmethod
    def _compute_signature(url: str, observations: list[RawElementObservation]) -> str:
        parts = [url]
        for obs in sorted(
            observations, key=lambda o: (o.tag, o.html_id or "", o.name or "", o.role or "")
        ):
            parts.append(
                f"{obs.tag}|{obs.html_id or ''}|{obs.name or ''}|{obs.role or ''}|"
                f"{obs.accessible_name or ''}"
            )
        return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
