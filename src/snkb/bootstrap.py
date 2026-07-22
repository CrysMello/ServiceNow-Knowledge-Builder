"""Composition root: único local autorizado a escolher implementações
concretas para os ports da aplicação (AI Coding Standards, seção 10).

``create_controller`` carrega a configuração (via Configuration
Manager, ADR 0015), constrói os adaptadores do Log Engine, Session
Manager, Navigation Recorder, Element Recorder, Selector Analyzer,
Screenshot Engine, Export Engine, Session Discovery, Folder Opener e
Log Reader (ADR 0014), monta uma fábrica de Browser Manager (uma
instância nova por sessão, ADR 0004), uma fábrica de Browser Data
Collector (ADR 0013) e devolve um ``ApplicationController`` (ADR 0012)
pronto para uso. O ponto de entrada real da aplicação é a CLI
(``snkb.presentation.cli.main:main``, registrado em
``[project.scripts]``), que injeta o controller retornado aqui em cada
handler de comando (ver ADR 0003).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from snkb.application.services.application_controller import (
    ApplicationController,
    InMemoryEventBus,
    InMemoryScreenshotStore,
)
from snkb.infrastructure.browser.browser_data_collector import BrowserDataCollector
from snkb.infrastructure.browser.browser_manager import PlaywrightBrowserManager
from snkb.infrastructure.configuration.configuration_manager import JsonConfigurationProvider
from snkb.infrastructure.logging.log_engine import LoguruLogEngine
from snkb.infrastructure.logging.log_reader import DiskLogReader
from snkb.infrastructure.storage.folder_opener import OsFolderOpener
from snkb.infrastructure.storage.session_discovery import DiskSessionDiscovery
from snkb.modules.elements.element_recorder import ElementRecorder
from snkb.modules.export.export_engine import ExportEngine
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.modules.screenshots.screenshot_engine import ScreenshotEngine
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer
from snkb.modules.session.session_manager import SessionManager

if TYPE_CHECKING:
    from snkb.application.ports.browser_manager_port import BrowserManagerPort
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.application.services.application_controller_port import (
        ApplicationControllerPort,
    )

_CONFIG_CANDIDATES = (Path("config/local.json"), Path("config/default.json"))
_LOG_DIRECTORY = Path("logs")


def create_controller() -> ApplicationControllerPort:
    """Monta todos os adaptadores e retorna o ``ApplicationControllerPort``
    pronto para uso pelos comandos da CLI."""
    config = JsonConfigurationProvider(candidates=_CONFIG_CANDIDATES).load()

    log_engine = LoguruLogEngine(
        log_directory=_LOG_DIRECTORY,
        log_level=config.log_level,
        retention_days=config.log_retention_days,
    )
    event_bus = InMemoryEventBus(log_engine)
    screenshot_store = InMemoryScreenshotStore()
    session_discovery = DiskSessionDiscovery(
        output_directory=config.output_directory, log_engine=log_engine
    )
    folder_opener = OsFolderOpener()
    log_reader = DiskLogReader(log_directory=_LOG_DIRECTORY)

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
        session_id: UUID, event_publisher: EventPublisherPort, log_engine_for_session: LogEnginePort
    ) -> BrowserManagerPort:
        return PlaywrightBrowserManager(
            session_id=session_id,
            config=config,
            event_publisher=event_publisher,
            log_engine=log_engine_for_session,
        )

    def browser_data_collector_factory(browser_manager: BrowserManagerPort) -> BrowserDataCollector:
        return BrowserDataCollector(
            browser_manager=browser_manager,
            navigation_recorder=navigation_recorder,
            element_recorder=element_recorder,
            selector_analyzer=selector_analyzer,
            screenshot_engine=screenshot_engine,
            session_manager=session_manager,
            event_bus=event_bus,
            log_engine=log_engine,
            screenshot_store=screenshot_store,
            config=config,
        )

    return ApplicationController(
        session_manager=session_manager,
        navigation_recorder=navigation_recorder,
        element_recorder=element_recorder,
        selector_analyzer=selector_analyzer,
        screenshot_engine=screenshot_engine,
        export_engine=export_engine,
        log_engine=log_engine,
        event_bus=event_bus,
        session_discovery=session_discovery,
        folder_opener=folder_opener,
        log_reader=log_reader,
        config=config,
        browser_manager_factory=browser_manager_factory,
        browser_data_collector_factory=browser_data_collector_factory,
    )


__all__ = ["create_controller"]
