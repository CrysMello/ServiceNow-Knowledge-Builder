"""Composition root: único local autorizado a escolher implementações
concretas para os ports da aplicação (AI Coding Standards, seção 10).

``create_controller`` carrega a configuração, constrói os adaptadores
do Log Engine, Session Manager, Navigation Recorder, Element Recorder,
Selector Analyzer, Screenshot Engine e Export Engine, monta uma fábrica
de Browser Manager (uma instância nova por sessão, ADR 0004), uma
fábrica de Browser Data Collector (ADR 0013) e devolve um
``ApplicationController`` (ADR 0012) pronto para uso. O ponto de
entrada real da aplicação é a CLI
(``snkb.presentation.cli.main:main``, registrado em
``[project.scripts]``), que injeta o controller retornado aqui em cada
handler de comando (ver ADR 0003).

O carregamento de configuração aqui é deliberadamente mínimo — lê
``config/local.json`` (se existir) ou ``config/default.json`` e valida
via ``AppConfig``. Isso NÃO é uma implementação de
``ConfigurationProviderPort`` (Configuration Manager, item separado do
checklist em ``docs/module-specs/README.md``): não há recarregamento
em tempo de execução nem mensagens de erro por campo (CFG-006). Ver
ADR 0012, "Consequências".
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
from snkb.infrastructure.logging.log_engine import LoguruLogEngine
from snkb.modules.elements.element_recorder import ElementRecorder
from snkb.modules.export.export_engine import ExportEngine
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.modules.screenshots.screenshot_engine import ScreenshotEngine
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer
from snkb.modules.session.session_manager import SessionManager
from snkb.shared.dtos.app_config import AppConfig

if TYPE_CHECKING:
    from snkb.application.ports.browser_manager_port import BrowserManagerPort
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.application.services.application_controller_port import (
        ApplicationControllerPort,
    )

_CONFIG_CANDIDATES = (Path("config/local.json"), Path("config/default.json"))


def _load_config() -> AppConfig:
    for candidate in _CONFIG_CANDIDATES:
        if candidate.is_file():
            return AppConfig.model_validate_json(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "snkb: nenhum arquivo de configuração encontrado "
        f"({', '.join(str(path) for path in _CONFIG_CANDIDATES)}). "
        "Copie config/default.json para config/local.json e ajuste instance_url/"
        "output_directory antes de gravar uma sessão real."
    )


def create_controller() -> ApplicationControllerPort:
    """Monta todos os adaptadores e retorna o ``ApplicationControllerPort``
    pronto para uso pelos comandos da CLI."""
    config = _load_config()

    log_engine = LoguruLogEngine(
        log_directory=Path("logs"),
        log_level=config.log_level,
        retention_days=config.log_retention_days,
    )
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
        browser_manager_factory=browser_manager_factory,
        browser_data_collector_factory=browser_data_collector_factory,
    )


__all__ = ["create_controller"]
