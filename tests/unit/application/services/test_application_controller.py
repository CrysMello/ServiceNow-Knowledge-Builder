"""Testes do ``ApplicationController`` (Module Specifications 2.5,
ARQ-002; ADR 0012).

Usa os módulos reais de dados (Session Manager, Navigation Recorder,
Element Recorder, Selector Analyzer, Screenshot Engine, Export Engine —
todos síncronos, sem I/O real, já testados isoladamente em seus
próprios módulos) e um Browser Manager falso (o único módulo que
exigiria um Chromium real — ver ``tests/integration/
test_application_controller_integration.py`` para o caminho com
Playwright de verdade). O ``dispatch()`` de ``StartCapture`` roda em
uma thread real de segundo plano (como em produção); os testes
esperam pela conclusão via polling curto, nunca via ``sleep`` fixo.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from snkb.application.commands.commands import (
    ExitApplication,
    OpenExportFolder,
    PauseCapture,
    ResumeCapture,
    StartCapture,
    StopCapture,
)
from snkb.application.ports.log_reader_port import LogRecordSummary
from snkb.application.ports.session_discovery_port import SessionSummary
from snkb.application.queries.queries import (
    GetEffectiveConfiguration,
    GetNavigationTimeline,
    GetRecentSessions,
    GetSessionLogs,
    GetSessionStatistics,
    GetSessionStatus,
    ValidateExport,
)
from snkb.application.services.application_controller import (
    ApplicationController,
    InMemoryEventBus,
)
from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.events.export_events import ExportFailed
from snkb.domain.events.session_events import SessionCreated, SessionStarted
from snkb.domain.events.system_events import ErrorOccurred
from snkb.domain.exceptions.application_exceptions import CaptureAlreadyActiveError
from snkb.modules.elements.element_recorder import ElementRecorder
from snkb.modules.export.export_engine import ExportEngine
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.modules.screenshots.screenshot_engine import ScreenshotEngine
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer
from snkb.modules.session.session_manager import SessionManager
from snkb.shared.dtos.app_config import AppConfig, CapturePolicyModel

_INSTANCE_URL = "https://empresa.service-now.com"
_POLL_TIMEOUT_SECONDS = 2.0
_POLL_INTERVAL_SECONDS = 0.01


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
        return {"total_entries": len(self.messages)}


class _FakeBrowserManager:
    """Duplo de teste de ``BrowserManagerPort``.

    ``open_url`` publica um ``PageChanged`` de forma síncrona — como no
    Browser Manager real, a primeira navegação acontece *antes* do
    login, então antes de ``navigation_recorder.start()`` (ver ADR
    0012, "a primeira navegação sempre acontece antes do login"). Se
    ``second_navigation`` for ``True`` (padrão), ``wait_login`` também
    publica um segundo ``PageChanged`` pouco depois de retornar (via
    ``call_later``), simulando uma navegação real que já acontece com a
    gravação ativa."""

    def __init__(
        self,
        session_id: UUID,
        event_publisher: object,
        log_engine: object,
        *,
        initialize_error: Exception | None = None,
        login_error: Exception | None = None,
        never_login: bool = False,
        second_navigation: bool = True,
        call_order: list[str] | None = None,
    ) -> None:
        self.session_id = session_id
        self._event_publisher = event_publisher
        self._log = log_engine
        self.initialize_error = initialize_error
        self.login_error = login_error
        self.never_login = never_login
        self.second_navigation = second_navigation
        self._call_order = call_order

        self.initialized = False
        self.shutdown_called = False
        self.opened_urls: list[str] = []

    async def initialize(self) -> None:
        if self.initialize_error is not None:
            raise self.initialize_error
        self.initialized = True

    async def open_url(self, url: str) -> None:
        from snkb.domain.events.browser_events import PageChanged

        self.opened_urls.append(url)
        self._event_publisher.publish(  # type: ignore[attr-defined]
            PageChanged(session_id=self.session_id, url=url, tab_id="tab-1")
        )

    async def wait_login(self) -> None:
        if self.login_error is not None:
            raise self.login_error
        if self.never_login:
            await asyncio.Event().wait()  # nunca resolve por si só
            return
        if not self.second_navigation:
            return

        from snkb.domain.events.browser_events import PageChanged

        def _publish_navigation() -> None:
            self._event_publisher.publish(  # type: ignore[attr-defined]
                PageChanged(session_id=self.session_id, url=f"{_INSTANCE_URL}/list", tab_id="tab-1")
            )

        asyncio.get_running_loop().call_later(0.05, _publish_navigation)

    async def shutdown(self) -> None:
        self.shutdown_called = True
        if self._call_order is not None:
            self._call_order.append("browser_manager.shutdown")

    def current_page(self) -> object:
        return None

    def current_context(self) -> object:
        return None

    def browser_status(self) -> str:
        return "running" if self.initialized else "not_initialized"

    def current_tabs(self) -> list[object]:
        return []

    def is_alive(self) -> bool:
        return self.initialized and not self.shutdown_called

    async def restart(self) -> None:
        self.initialized = True

    async def close(self) -> None:
        await self.shutdown()


class _FakeBrowserDataCollector:
    """Duplo de teste de ``BrowserDataCollectorPort`` (ADR 0013) — só
    registra chamadas, sem tocar DOM/screenshot real."""

    def __init__(self, call_order: list[str] | None = None) -> None:
        self._call_order = call_order
        self.started_with: UUID | None = None
        self.start_calls = 0
        self.capture_calls = 0
        self.stop_calls = 0

    async def start(self, session_id: UUID) -> None:
        self.started_with = session_id
        self.start_calls += 1

    async def capture_current_page(self) -> object | None:
        self.capture_calls += 1
        return None

    async def stop(self) -> None:
        self.stop_calls += 1
        if self._call_order is not None:
            self._call_order.append("collector.stop")


class _FakeSessionDiscovery:
    """Duplo de teste de ``SessionDiscoveryPort`` (ADR 0014) — não toca
    disco, guarda ``SessionSummary`` fornecidos pelo teste."""

    def __init__(self, summaries: list[SessionSummary] | None = None) -> None:
        self.summaries = summaries or []

    def list_recent(self, limit: int = 20) -> list[SessionSummary]:
        return self.summaries[:limit]

    def find(self, session_id: UUID) -> SessionSummary | None:
        for summary in self.summaries:
            if summary.session_id == session_id:
                return summary
        return None


class _FakeFolderOpener:
    """Duplo de teste de ``FolderOpenerPort`` — só registra chamadas."""

    def __init__(self) -> None:
        self.opened: list[Path] = []

    def open(self, path: Path) -> None:
        self.opened.append(path)


class _FakeLogReader:
    """Duplo de teste de ``LogReaderPort`` — devolve registros
    pré-configurados pelo teste, sem ler arquivos."""

    def __init__(self, records: list[LogRecordSummary] | None = None) -> None:
        self.records = records or []

    def read_session_logs(self, session_id: UUID, limit: int = 200) -> list[LogRecordSummary]:
        return self.records[:limit]


def _wait_until(predicate: Callable[[], bool], timeout: float = _POLL_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise AssertionError(f"Condição não satisfeita após {timeout}s de espera.")


def _find_event[EventT](events: list[object], event_type: type[EventT]) -> EventT:
    for event in events:
        if isinstance(event, event_type):
            return event
    raise AssertionError(f"Nenhum evento do tipo {event_type.__name__} foi publicado.")


class _Harness:
    def __init__(
        self, tmp_path: Path, with_collector: bool = False, **browser_kwargs: object
    ) -> None:
        self.call_order: list[str] = []
        self.log_engine = _RecordingLogEngine()
        self.event_bus = InMemoryEventBus(self.log_engine)
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
            capture_policy=CapturePolicyModel(),
        )
        self.export_engine = ExportEngine(
            session_manager=self.session_manager,
            navigation_recorder=self.navigation_recorder,
            element_recorder=self.element_recorder,
            selector_analyzer=self.selector_analyzer,
            screenshot_engine=self.screenshot_engine,
            event_publisher=self.event_bus,
            log_engine=self.log_engine,
            output_directory=tmp_path,
        )

        self.browser_managers: list[_FakeBrowserManager] = []

        def factory(
            session_id: UUID, event_publisher: object, log_engine: object
        ) -> _FakeBrowserManager:
            manager = _FakeBrowserManager(
                session_id,
                event_publisher,
                log_engine,
                call_order=self.call_order,
                **browser_kwargs,
            )
            self.browser_managers.append(manager)
            return manager

        self.collectors: list[_FakeBrowserDataCollector] = []

        def collector_factory(_browser_manager: object) -> _FakeBrowserDataCollector:
            collector = _FakeBrowserDataCollector(call_order=self.call_order)
            self.collectors.append(collector)
            return collector

        self.session_discovery = _FakeSessionDiscovery()
        self.folder_opener = _FakeFolderOpener()
        self.log_reader = _FakeLogReader()
        self.config = AppConfig(instance_url=_INSTANCE_URL, output_directory=tmp_path)

        self.controller = ApplicationController(
            session_manager=self.session_manager,
            navigation_recorder=self.navigation_recorder,
            element_recorder=self.element_recorder,
            selector_analyzer=self.selector_analyzer,
            screenshot_engine=self.screenshot_engine,
            export_engine=self.export_engine,
            log_engine=self.log_engine,
            event_bus=self.event_bus,
            session_discovery=self.session_discovery,  # type: ignore[arg-type]
            folder_opener=self.folder_opener,  # type: ignore[arg-type]
            log_reader=self.log_reader,  # type: ignore[arg-type]
            config=self.config,
            browser_manager_factory=factory,  # type: ignore[arg-type]
            browser_data_collector_factory=collector_factory if with_collector else None,  # type: ignore[arg-type]
            shutdown_timeout_seconds=5.0,
        )

    def start_capture_and_get_session_id(self) -> UUID:
        """Dispara ``StartCapture`` e retorna o ``session_id`` assim que
        ``SessionCreated`` é publicado (síncrono, não espera o login)."""
        received: list[object] = []
        self.controller.subscribe(received.append)
        self.controller.dispatch(StartCapture(instance_url=_INSTANCE_URL))
        return _find_event(received, SessionCreated).session_id

    def start_and_wait_until_recording(self) -> UUID:
        received: list[object] = []
        self.controller.subscribe(received.append)
        self.controller.dispatch(StartCapture(instance_url=_INSTANCE_URL))
        _wait_until(lambda: any(isinstance(event, SessionStarted) for event in received))
        return _find_event(received, SessionStarted).session_id


def _make_harness(tmp_path: Path, **browser_kwargs: object) -> _Harness:
    return _Harness(tmp_path, **browser_kwargs)


# ----------------------------------------------------------------------
# StartCapture
# ----------------------------------------------------------------------


def test_start_capture_creates_session_and_reaches_recording(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    session_id = harness.start_and_wait_until_recording()

    assert harness.session_manager.get_session(session_id).status == SessionStatus.RECORDING
    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_start_capture_twice_raises(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    session_id = harness.start_and_wait_until_recording()

    with pytest.raises(CaptureAlreadyActiveError):
        harness.controller.dispatch(StartCapture(instance_url=_INSTANCE_URL))

    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_page_changed_after_login_is_captured_by_navigation_recorder(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    session_id = harness.start_and_wait_until_recording()

    _wait_until(lambda: len(harness.navigation_recorder.get_page_history()) == 2)

    pages = harness.navigation_recorder.get_page_history()
    assert pages[0].url.value == _INSTANCE_URL
    assert pages[1].url.value == f"{_INSTANCE_URL}/list"
    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_the_pre_login_page_is_captured_retroactively_once_recording_starts(
    tmp_path: Path,
) -> None:
    """A primeira navegação sempre acontece durante ``open_url()``,
    antes de ``navigation_recorder.start()`` (o login ainda nem
    começou) — sem o cache de ``_last_page_event``, essa página nunca
    seria capturada quando não há navegação alguma depois do login."""
    harness = _make_harness(tmp_path, second_navigation=False)
    session_id = harness.start_and_wait_until_recording()

    _wait_until(lambda: len(harness.navigation_recorder.get_page_history()) == 1)

    pages = harness.navigation_recorder.get_page_history()
    assert pages[0].url.value == _INSTANCE_URL
    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_start_capture_failure_publishes_error_and_cancels_session(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path, initialize_error=RuntimeError("Chromium indisponível"))
    received: list[object] = []
    harness.controller.subscribe(received.append)

    harness.controller.dispatch(StartCapture(instance_url=_INSTANCE_URL))

    _wait_until(lambda: any(isinstance(event, ErrorOccurred) for event in received))
    session_id = _find_event(received, SessionCreated).session_id
    _wait_until(
        lambda: harness.session_manager.get_session(session_id).status == SessionStatus.INTERRUPTED
    )
    assert harness.browser_managers[0].shutdown_called is True


# ----------------------------------------------------------------------
# StopCapture
# ----------------------------------------------------------------------


def test_stop_capture_shuts_down_browser_and_attempts_export(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    session_id = harness.start_and_wait_until_recording()
    received: list[object] = []
    harness.controller.subscribe(received.append)

    harness.controller.dispatch(StopCapture(session_id=session_id))

    session = harness.session_manager.get_session(session_id)
    assert session.status in (
        SessionStatus.COMPLETED,
        SessionStatus.COMPLETED_WITH_WARNINGS,
    )
    assert harness.browser_managers[0].shutdown_called is True
    # Metadados de navegador (browser/resolução/viewport) nunca foram
    # coletados nesta etapa (ADR 0012) — a exportação falha de forma
    # honesta, não fabrica um session.json incompleto.
    assert any(isinstance(event, ExportFailed) for event in received)


# ----------------------------------------------------------------------
# Browser Data Collector (ADR 0013)
# ----------------------------------------------------------------------


def test_collector_is_started_and_seeded_with_the_first_page(tmp_path: Path) -> None:
    harness = _Harness(tmp_path, with_collector=True)
    session_id = harness.start_and_wait_until_recording()

    _wait_until(lambda: len(harness.collectors) == 1 and harness.collectors[0].start_calls == 1)

    collector = harness.collectors[0]
    assert collector.started_with == session_id
    assert collector.capture_calls >= 1

    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_collector_stops_before_the_browser_manager_shuts_down(tmp_path: Path) -> None:
    harness = _Harness(tmp_path, with_collector=True)
    session_id = harness.start_and_wait_until_recording()
    _wait_until(lambda: len(harness.collectors) == 1)

    harness.controller.dispatch(StopCapture(session_id=session_id))

    assert harness.collectors[0].stop_calls == 1
    assert harness.browser_managers[0].shutdown_called is True
    assert harness.call_order == ["collector.stop", "browser_manager.shutdown"]


def test_without_a_collector_factory_capture_still_works(tmp_path: Path) -> None:
    """``browser_data_collector_factory`` é opcional (``None`` por
    padrão) — o restante do fluxo (Browser Manager, Navigation
    Recorder, exportação) precisa continuar funcionando exatamente como
    antes da ADR 0013 quando nenhum coletor é injetado."""
    harness = _make_harness(tmp_path)  # sem with_collector=True

    session_id = harness.start_and_wait_until_recording()
    harness.controller.dispatch(StopCapture(session_id=session_id))

    assert harness.collectors == []
    assert harness.browser_managers[0].shutdown_called is True


def test_stop_capture_during_login_wait_cancels_without_recording(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path, never_login=True)
    session_id = harness.start_capture_and_get_session_id()
    _wait_until(
        lambda: len(harness.browser_managers) == 1 and harness.browser_managers[0].initialized
    )

    harness.controller.dispatch(StopCapture(session_id=session_id))

    assert harness.session_manager.get_session(session_id).status == SessionStatus.INTERRUPTED
    assert harness.browser_managers[0].shutdown_called is True
    assert harness.navigation_recorder.get_current_page() is None


# ----------------------------------------------------------------------
# Pause / Resume / ExitApplication
# ----------------------------------------------------------------------


def test_pause_and_resume_capture(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    session_id = harness.start_and_wait_until_recording()

    harness.controller.dispatch(PauseCapture(session_id=session_id))
    assert harness.session_manager.get_session(session_id).status == SessionStatus.PAUSED

    harness.controller.dispatch(ResumeCapture(session_id=session_id))
    assert harness.session_manager.get_session(session_id).status == SessionStatus.RECORDING

    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_exit_application_stops_the_active_capture(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    session_id = harness.start_and_wait_until_recording()

    harness.controller.dispatch(ExitApplication())

    assert harness.browser_managers[0].shutdown_called is True
    assert harness.session_manager.get_session(session_id).status in (
        SessionStatus.COMPLETED,
        SessionStatus.COMPLETED_WITH_WARNINGS,
    )


def test_exit_application_without_active_capture_is_a_no_op(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    harness.controller.dispatch(ExitApplication())  # não deve levantar


# ----------------------------------------------------------------------
# query()
# ----------------------------------------------------------------------


def test_query_get_session_status(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    session_id = harness.start_and_wait_until_recording()

    status = harness.controller.query(GetSessionStatus(session_id=session_id))

    assert status == "recording"
    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_query_get_session_statistics(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path, second_navigation=False)
    session_id = harness.start_and_wait_until_recording()
    _wait_until(lambda: len(harness.navigation_recorder.get_page_history()) == 1)

    stats = harness.controller.query(GetSessionStatistics(session_id=session_id))

    assert isinstance(stats, dict)
    assert stats["page_count"] == 1
    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_query_get_navigation_timeline(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path, second_navigation=False)
    session_id = harness.start_and_wait_until_recording()
    _wait_until(lambda: len(harness.navigation_recorder.get_page_history()) == 1)

    timeline = harness.controller.query(GetNavigationTimeline(session_id=session_id))

    assert isinstance(timeline, list)
    assert len(timeline) == 1
    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_query_get_recent_sessions_delegates_to_session_discovery(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    summary = SessionSummary(
        session_id=UUID(int=1),
        status="completed",
        instance_url=_INSTANCE_URL,
        export_directory=tmp_path / "1",
        recording_start=datetime.now(UTC),
        recording_end=None,
        total_pages=1,
        total_elements=2,
        total_screenshots=3,
        error_count=0,
    )
    harness.session_discovery.summaries = [summary]

    result = harness.controller.query(GetRecentSessions(limit=5))

    assert result == [summary]


def test_query_validate_export_delegates_to_export_engine(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    session_id = harness.start_and_wait_until_recording()
    harness.controller.dispatch(StopCapture(session_id=session_id))

    # Exportação falha de forma honesta nesta harness (sem metadados de
    # navegador) — validate() deve refletir isso, não fabricar sucesso.
    assert harness.controller.query(ValidateExport(session_id=session_id)) is False


def test_query_get_session_logs_delegates_to_log_reader(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    record = LogRecordSummary(
        timestamp=datetime.now(UTC), level="INFO", module="session_manager", message="oi"
    )
    harness.log_reader.records = [record]

    result = harness.controller.query(GetSessionLogs(session_id=UUID(int=1)))

    assert result == [record]


def test_query_get_effective_configuration_returns_injected_config(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    assert harness.controller.query(GetEffectiveConfiguration()) is harness.config


def test_dispatch_open_export_folder_opens_the_discovered_directory(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    export_dir = tmp_path / "export"
    summary = SessionSummary(
        session_id=UUID(int=1),
        status="completed",
        instance_url=_INSTANCE_URL,
        export_directory=export_dir,
        recording_start=datetime.now(UTC),
        recording_end=None,
        total_pages=0,
        total_elements=0,
        total_screenshots=0,
        error_count=0,
    )
    harness.session_discovery.summaries = [summary]

    harness.controller.dispatch(OpenExportFolder(session_id=UUID(int=1)))

    assert harness.folder_opener.opened == [export_dir]


def test_dispatch_open_export_folder_publishes_error_when_session_not_found(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    received: list[object] = []
    harness.controller.subscribe(received.append)

    harness.controller.dispatch(OpenExportFolder(session_id=UUID(int=99)))

    assert harness.folder_opener.opened == []
    assert any(isinstance(event, ErrorOccurred) for event in received)


def test_dispatch_unknown_command_raises_not_implemented(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    with pytest.raises(NotImplementedError):
        harness.controller.dispatch(object())


def test_query_unknown_raises_not_implemented(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    with pytest.raises(NotImplementedError):
        harness.controller.query(object())


# ----------------------------------------------------------------------
# subscribe() / InMemoryEventBus
# ----------------------------------------------------------------------


def test_subscribe_receives_session_created_synchronously(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    received: list[object] = []
    harness.controller.subscribe(received.append)

    harness.controller.dispatch(StartCapture(instance_url=_INSTANCE_URL))

    assert any(isinstance(event, SessionCreated) for event in received)
    session_id = _find_event(received, SessionCreated).session_id
    _wait_until(
        lambda: harness.session_manager.get_session(session_id).status == SessionStatus.RECORDING
    )
    harness.controller.dispatch(StopCapture(session_id=session_id))


def test_event_bus_error_in_one_subscriber_does_not_prevent_others() -> None:
    log_engine = _RecordingLogEngine()
    bus = InMemoryEventBus(log_engine)
    received: list[object] = []

    def _failing_subscriber(event: object) -> None:
        raise RuntimeError("assinante quebrado")

    bus.subscribe(_failing_subscriber)
    bus.subscribe(received.append)

    bus.publish(SessionCreated(session_id=UUID(int=1)))

    assert len(received) == 1
    assert any("assinante" in message.lower() for message in log_engine.messages)
