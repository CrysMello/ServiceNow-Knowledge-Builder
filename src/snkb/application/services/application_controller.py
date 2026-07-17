"""Implementação concreta de ``ApplicationControllerPort`` — o
composition root que conecta Browser Manager, Browser Data Collector,
Session Manager, Navigation Recorder, Element Recorder, Selector
Analyzer, Screenshot Engine, Export Engine e Log Engine (Module
Specifications 2.5, ARQ-002).

Único ponto de entrada que a camada de apresentação pode chamar
(``dispatch``/``query``/``subscribe``). Nenhum módulo de infraestrutura
concreto é importado aqui — apenas Protocols (`application.ports`) e
tipos de domínio; quem escolhe as implementações concretas é
``bootstrap.py``. Ver ADR 0012 para a ponte entre o laço de eventos
assíncrono do Playwright (dentro de uma thread em segundo plano) e o
``dispatch()`` síncrono que a CLI espera, e ADR 0013 para o Browser
Data Collector e a ordem de encerramento revisada (captura final antes
de fechar o navegador).
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from snkb.application.commands.commands import (
    ExitApplication,
    PauseCapture,
    ResumeCapture,
    StartCapture,
    StopCapture,
)
from snkb.application.queries.queries import (
    GetNavigationTimeline,
    GetRecentSessions,
    GetSessionStatistics,
    GetSessionStatus,
)
from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.events.browser_events import PageChanged
from snkb.domain.events.system_events import ErrorOccurred
from snkb.domain.exceptions.application_exceptions import CaptureAlreadyActiveError

if TYPE_CHECKING:
    from collections.abc import Callable

    from snkb.application.ports.browser_data_collector_port import BrowserDataCollectorPort
    from snkb.application.ports.browser_manager_port import BrowserManagerPort
    from snkb.application.ports.element_recorder_port import ElementRecorderPort
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.export_engine_port import ExportEnginePort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.application.ports.navigation_recorder_port import NavigationRecorderPort
    from snkb.application.ports.screenshot_engine_port import ScreenshotEnginePort
    from snkb.application.ports.selector_analyzer_port import SelectorAnalyzerPort
    from snkb.application.ports.session_manager_port import SessionManagerPort
    from snkb.domain.events.base import DomainEvent

    class _JoinableThread(Protocol):
        def start(self) -> None: ...
        def join(self, timeout: float | None = None) -> None: ...

    class _SessionManagerWithLifecycleHooks(SessionManagerPort, Protocol):
        """``SessionManager`` expõe transições intermediárias
        (``mark_preparing``/``mark_waiting_authentication``/``mark_ready``)
        além da superfície mínima do Port — ver ADR 0005."""

        def mark_preparing(self, session_id: UUID) -> None: ...
        def mark_waiting_authentication(self, session_id: UUID) -> None: ...
        def mark_ready(self, session_id: UUID) -> None: ...

    class _NavigationRecorderWithObservation(NavigationRecorderPort, Protocol):
        """``NavigationRecorder`` expõe ``observe_navigation`` além da
        superfície mínima do Port — ver ADR 0006."""

        def observe_navigation(self, tab_id: str, url: str, title: str | None = None) -> None: ...


_DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 30.0
_RECORDING_STATUSES = frozenset({SessionStatus.RECORDING, SessionStatus.PAUSED})


def _default_thread_factory(target: Callable[[], None]) -> _JoinableThread:
    return threading.Thread(target=target, daemon=True)


class InMemoryEventBus:
    """Publica eventos a todos os assinantes registrados. Um erro em um
    assinante nunca impede que os demais recebam o evento (AI Coding
    Standards, seção 12) — a exceção é registrada via ``LogEnginePort``
    e o laço continua.

    Público (não prefixado com ``_``) porque ``bootstrap.py`` precisa
    construir uma única instância e injetá-la em todos os módulos de
    dados (Session Manager, Navigation Recorder, ...) além do próprio
    ``ApplicationController`` — todos precisam compartilhar o mesmo
    barramento para que eventos como ``SessionStarted``/``PageCaptured``/
    ``ExportCompleted`` cheguem à CLI (ver ADR 0012)."""

    def __init__(self, log_engine: LogEnginePort) -> None:
        self._log = log_engine
        self._subscribers: list[Callable[[DomainEvent], None]] = []

    def subscribe(self, handler: Callable[[DomainEvent], None]) -> None:
        self._subscribers.append(handler)

    def publish(self, event: DomainEvent) -> None:
        for subscriber in list(self._subscribers):
            try:
                subscriber(event)
            except Exception:
                self._log.exception(
                    "Erro ao processar evento em um assinante; os demais "
                    "assinantes não são afetados.",
                    event_type=type(event).__name__,
                )


class InMemoryScreenshotStore:
    """Guarda os bytes reais de screenshots, indexados por
    ``screenshot_id``. O Screenshot Engine (ADR 0009) nunca vê o
    conteúdo binário — só o Browser Data Collector (que efetivamente
    chama ``page.screenshot()``, ADR 0013) escreve aqui; o Export
    Engine (ADR 0010) só lê, via ``screenshot_bytes_provider``.

    Público pelo mesmo motivo de ``InMemoryEventBus``: ``bootstrap.py``
    constrói uma única instância e a injeta tanto na fábrica do coletor
    quanto no Export Engine."""

    def __init__(self) -> None:
        self._bytes_by_id: dict[UUID, bytes] = {}

    def put(self, screenshot_id: UUID, data: bytes) -> None:
        self._bytes_by_id[screenshot_id] = data

    def get(self, screenshot_id: UUID) -> bytes | None:
        return self._bytes_by_id.get(screenshot_id)


class ApplicationController:
    """Composition root em tempo de execução: dispatcha comandos, atende
    consultas e conecta os oito módulos centrais via um barramento de
    eventos em memória compartilhado."""

    def __init__(
        self,
        session_manager: _SessionManagerWithLifecycleHooks,
        navigation_recorder: _NavigationRecorderWithObservation,
        element_recorder: ElementRecorderPort,
        selector_analyzer: SelectorAnalyzerPort,
        screenshot_engine: ScreenshotEnginePort,
        export_engine: ExportEnginePort,
        log_engine: LogEnginePort,
        event_bus: InMemoryEventBus,
        browser_manager_factory: Callable[
            [UUID, EventPublisherPort, LogEnginePort], BrowserManagerPort
        ],
        browser_data_collector_factory: (
            Callable[[BrowserManagerPort], BrowserDataCollectorPort] | None
        ) = None,
        thread_factory: Callable[[Callable[[], None]], _JoinableThread] = _default_thread_factory,
        shutdown_timeout_seconds: float = _DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
    ) -> None:
        self._session_manager = session_manager
        self._navigation_recorder = navigation_recorder
        self._element_recorder = element_recorder
        self._selector_analyzer = selector_analyzer
        self._screenshot_engine = screenshot_engine
        self._export_engine = export_engine
        self._log = log_engine
        self._browser_manager_factory = browser_manager_factory
        self._browser_data_collector_factory = browser_data_collector_factory
        self._thread_factory = thread_factory
        self._shutdown_timeout_seconds = shutdown_timeout_seconds

        self._event_bus = event_bus
        self._event_bus.subscribe(self._on_domain_event)

        self._active_session_id: UUID | None = None
        self._browser_managers: dict[UUID, BrowserManagerPort] = {}
        self._collectors: dict[UUID, BrowserDataCollectorPort] = {}
        self._threads: dict[UUID, _JoinableThread] = {}
        self._stop_events: dict[UUID, asyncio.Event] = {}
        self._loops: dict[UUID, asyncio.AbstractEventLoop] = {}
        self._navigation_active_session_id: UUID | None = None
        self._last_page_event: dict[UUID, PageChanged] = {}

    # ------------------------------------------------------------------
    # ApplicationControllerPort
    # ------------------------------------------------------------------

    def subscribe(self, handler: Callable[[DomainEvent], None]) -> None:
        self._event_bus.subscribe(handler)

    def dispatch(self, command: object) -> None:
        match command:
            case StartCapture(instance_url=instance_url):
                self._handle_start_capture(instance_url)
            case StopCapture(session_id=session_id):
                self._handle_stop_capture(session_id)
            case PauseCapture(session_id=session_id):
                self._session_manager.pause_session(session_id)
            case ResumeCapture(session_id=session_id):
                self._session_manager.resume_session(session_id)
            case ExitApplication():
                self._handle_exit_application()
            case _:
                raise NotImplementedError(
                    f"Comando ainda não suportado pelo Application Controller: "
                    f"{type(command).__name__}"
                )

    def query(self, query: object) -> object:
        match query:
            case GetSessionStatus(session_id=session_id):
                return self._session_manager.get_session(session_id).status.value
            case GetSessionStatistics(session_id=session_id):
                return self._build_live_statistics(session_id)
            case GetNavigationTimeline():
                return self._navigation_recorder.export_navigation().get("timeline", [])
            case GetRecentSessions():
                raise NotImplementedError(
                    "GetRecentSessions depende de um mecanismo de descoberta de "
                    "sessões persistidas em disco (Configuration Manager/leitura "
                    "de exports/), ainda não implementado."
                )
            case _:
                raise NotImplementedError(
                    f"Consulta ainda não suportada pelo Application Controller: "
                    f"{type(query).__name__}"
                )

    # ------------------------------------------------------------------
    # StartCapture
    # ------------------------------------------------------------------

    def _handle_start_capture(self, instance_url: str) -> None:
        if self._active_session_id is not None:
            raise CaptureAlreadyActiveError(
                f"Já existe uma gravação em andamento (sessão {self._active_session_id})."
            )

        session = self._session_manager.create_session(instance_url)
        session_id = session.session_id.value
        self._active_session_id = session_id

        thread = self._thread_factory(lambda: self._run_capture_flow_sync(session_id, instance_url))
        self._threads[session_id] = thread
        thread.start()

    def _run_capture_flow_sync(self, session_id: UUID, instance_url: str) -> None:
        asyncio.run(self._run_capture_flow(session_id, instance_url))

    async def _run_capture_flow(self, session_id: UUID, instance_url: str) -> None:
        stop_event = asyncio.Event()
        self._loops[session_id] = asyncio.get_running_loop()
        self._stop_events[session_id] = stop_event

        browser_manager: BrowserManagerPort | None = None
        try:
            browser_manager = self._browser_manager_factory(session_id, self._event_bus, self._log)
            self._browser_managers[session_id] = browser_manager

            self._session_manager.mark_preparing(session_id)
            await browser_manager.initialize()
            await browser_manager.open_url(instance_url)
            self._session_manager.mark_waiting_authentication(session_id)

            if not await self._wait_for_login_or_stop(browser_manager, stop_event):
                return  # StopCapture chegou antes de o login ser detectado.

            self._session_manager.mark_ready(session_id)
            self._session_manager.start_session(session_id)
            self._navigation_recorder.start(session_id)
            self._navigation_active_session_id = session_id
            self._capture_last_known_page(session_id)

            if self._browser_data_collector_factory is not None:
                collector = self._browser_data_collector_factory(browser_manager)
                self._collectors[session_id] = collector
                await collector.start(session_id)
                with contextlib.suppress(Exception):
                    await collector.capture_current_page()

            await stop_event.wait()
        except Exception as error:
            self._log.exception("Falha durante a captura.", session_id=str(session_id))
            self._event_bus.publish(
                ErrorOccurred(
                    session_id=session_id,
                    module="ApplicationController",
                    message=str(error),
                )
            )
            with contextlib.suppress(Exception):
                self._session_manager.cancel_session(session_id)
        finally:
            # ADR 0013: o coletor precisa do navegador vivo para uma
            # última captura/screenshot — por isso encerra ANTES de
            # fechar o navegador, mesmo em caminhos de falha.
            active_collector = self._collectors.get(session_id)
            if active_collector is not None:
                with contextlib.suppress(Exception):
                    await active_collector.stop()
            if browser_manager is not None:
                with contextlib.suppress(Exception):
                    await browser_manager.shutdown()

    @staticmethod
    async def _wait_for_login_or_stop(
        browser_manager: BrowserManagerPort, stop_event: asyncio.Event
    ) -> bool:
        """Retorna ``True`` se o login foi detectado, ``False`` se
        ``StopCapture`` chegou primeiro (RN-005: Ctrl+C durante o login
        deve encerrar sem tentar iniciar a gravação)."""
        login_task = asyncio.ensure_future(browser_manager.wait_login())
        stop_task = asyncio.ensure_future(stop_event.wait())
        done, pending = await asyncio.wait(
            {login_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if stop_task in done:
            login_task.cancel()
            return False
        login_task.result()
        return True

    # ------------------------------------------------------------------
    # StopCapture
    # ------------------------------------------------------------------

    def _handle_stop_capture(self, session_id: UUID) -> None:
        self._signal_stop_and_wait(session_id)

        session = self._session_manager.get_session(session_id)
        if session.status in _RECORDING_STATUSES:
            self._navigation_recorder.stop()
            self._session_manager.finish_session(session_id)
            try:
                self._export_engine.export(session_id)
            except Exception as error:
                self._log.warning(f"Exportação falhou: {error}", session_id=str(session_id))
        elif self._session_manager.is_active(session_id):
            self._session_manager.cancel_session(session_id)

        self._cleanup_session_state(session_id)

    def _signal_stop_and_wait(self, session_id: UUID) -> None:
        stop_event = self._stop_events.get(session_id)
        loop = self._loops.get(session_id)
        if stop_event is not None and loop is not None:
            loop.call_soon_threadsafe(stop_event.set)

        thread = self._threads.get(session_id)
        if thread is not None:
            thread.join(timeout=self._shutdown_timeout_seconds)

    def _cleanup_session_state(self, session_id: UUID) -> None:
        self._stop_events.pop(session_id, None)
        self._loops.pop(session_id, None)
        self._browser_managers.pop(session_id, None)
        self._collectors.pop(session_id, None)
        self._threads.pop(session_id, None)
        self._last_page_event.pop(session_id, None)
        if self._navigation_active_session_id == session_id:
            self._navigation_active_session_id = None
        if self._active_session_id == session_id:
            self._active_session_id = None

    def _handle_exit_application(self) -> None:
        if self._active_session_id is not None:
            self._handle_stop_capture(self._active_session_id)

    # ------------------------------------------------------------------
    # Coordenação entre módulos (assinante interno do barramento)
    # ------------------------------------------------------------------

    def _on_domain_event(self, event: DomainEvent) -> None:
        """Encaminha eventos do Browser Manager para o Navigation
        Recorder — a ligação automática que este controller estabelece
        diretamente. O Browser Data Collector (ADR 0013), quando
        presente, se assina ao mesmo barramento por conta própria
        (dentro de ``BrowserDataCollector.start()``) para alimentar
        Element Recorder, Selector Analyzer e Screenshot Engine — este
        método não precisa (nem deve) saber disso.

        A primeira navegação de uma sessão sempre acontece durante
        ``open_url()``, antes de ``navigation_recorder.start()`` (que só
        roda depois do login) — por isso todo ``PageChanged`` é
        guardado em ``_last_page_event`` independentemente de a
        gravação já estar ativa; ``_capture_last_known_page`` usa esse
        cache assim que a gravação realmente começa."""
        if isinstance(event, PageChanged):
            self._last_page_event[event.session_id] = event
            if event.session_id == self._navigation_active_session_id:
                self._navigation_recorder.observe_navigation(tab_id=event.tab_id, url=event.url)
                self._navigation_recorder.capture_page()

    def _capture_last_known_page(self, session_id: UUID) -> None:
        cached = self._last_page_event.get(session_id)
        if cached is not None:
            self._navigation_recorder.observe_navigation(tab_id=cached.tab_id, url=cached.url)
            self._navigation_recorder.capture_page()

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def _build_live_statistics(self, session_id: UUID) -> dict[str, object]:
        session_stats = self._session_manager.get_statistics(session_id)
        element_stats = self._element_recorder.get_statistics()
        screenshot_stats = self._screenshot_engine.statistics()
        log_stats = self._log.statistics()
        return {
            **session_stats,
            "page_count": len(self._navigation_recorder.get_page_history()),
            "element_count": element_stats.get("total_elements", 0),
            "screenshot_count": screenshot_stats.get("total_screenshots", 0),
            "log_count": log_stats.get("total_entries", 0),
        }
