"""Teste de aceite ponta a ponta (SRS, Capítulo 8: "Iniciar uma
gravação", "Navegar e capturar dados", "Encerrar e exportar"): um app
HTML local determinístico de quatro páginas (login simulado, home,
lista de planos de teste, formulário de cadastro), Chromium real,
sem depender da internet, do Microsoft SSO ou de uma instância real do
ServiceNow (AI Coding Standards, seção 19).

Orquestra os módulos diretamente (Session/Navigation/Element/Selector/
Screenshot/Export Engine + Browser Manager + Browser Data Collector),
no mesmo laço de eventos do teste — o mesmo padrão comprovado em
``tests/integration/test_browser_data_collector_integration.py``. A
travessia da ``ApplicationController`` (thread em segundo plano com
seu próprio laço asyncio) já é validada isoladamente em
``tests/integration/test_application_controller_integration.py``; este
teste foca em validar a Base de Conhecimento exportada ao final de uma
sessão real com múltiplas páginas.

Requer ``playwright install chromium``. Se os binários do navegador
não estiverem instalados, o teste é pulado em vez de falhar.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Iterator
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import cast

import pytest
from playwright.async_api import Page
from typer.testing import CliRunner

from snkb.application.services.application_controller import (
    InMemoryEventBus,
    InMemoryScreenshotStore,
)
from snkb.domain.events.browser_events import PageChanged
from snkb.infrastructure.browser.browser_data_collector import BrowserDataCollector
from snkb.infrastructure.browser.browser_manager import PlaywrightBrowserManager
from snkb.modules.elements.element_recorder import ElementRecorder
from snkb.modules.export.export_engine import ExportEngine
from snkb.modules.navigation.navigation_recorder import NavigationRecorder
from snkb.modules.screenshots.screenshot_engine import ScreenshotEngine
from snkb.modules.selectors.selector_analyzer import SelectorAnalyzer
from snkb.modules.session.session_manager import SessionManager
from snkb.shared.dtos.app_config import AppConfig, CapturePolicyModel

_LOGIN_HTML = """
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Acesso - Instancia de Teste</title></head>
<body>
  <h1>Bem-vindo</h1>
  <a id="enter" href="home.html">Entrar</a>
</body>
</html>
"""

_HOME_HTML = """
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Pagina Inicial</title></head>
<body>
  <h1>Pagina Inicial</h1>
  <nav>
    <a id="nav-plans" href="plans.html">Planos de Teste</a>
    <a id="nav-register" href="register.html">Novo Cadastro</a>
  </nav>
</body>
</html>
"""

_PLANS_HTML = """
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Lista de Planos de Teste</title></head>
<body>
  <h1>Planos de Teste</h1>
  <table>
    <tr><td>Plano de Regressao</td><td><button id="view-plan-1">Ver</button></td></tr>
  </table>
  <a id="new-plan" href="register.html">Novo Plano</a>
</body>
</html>
"""

_REGISTER_HTML = """
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Cadastro de Plano de Teste</title></head>
<body>
  <h1>Cadastro de Plano de Teste</h1>
  <form>
    <input name="title" aria-label="Titulo do plano">
    <select name="category">
      <option value="functional">Funcional</option>
      <option value="performance">Performance</option>
    </select>
    <button id="submit-plan" type="submit">Salvar</button>
  </form>
</body>
</html>
"""

_PAGES = {
    "login.html": _LOGIN_HTML,
    "home.html": _HOME_HTML,
    "plans.html": _PLANS_HTML,
    "register.html": _REGISTER_HTML,
}


@pytest.fixture
def local_app_server(tmp_path: Path) -> Iterator[str]:
    """App HTML local de quatro páginas, servido só em 127.0.0.1."""
    for name, content in _PAGES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


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


async def _wait_until_async(predicate: object, timeout: float = 5.0) -> None:
    """Espera assíncrona até ``predicate()`` retornar verdadeiro —
    necessária porque o handler ``framenavigated`` do Playwright é
    despachado em uma iteração futura do laço de eventos, não
    garantidamente antes de ``page.goto()`` retornar."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"Condição não satisfeita após {timeout}s de espera.")


async def test_local_four_page_recording_flow_exports_real_knowledge_base(
    tmp_path: Path, local_app_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    login_url = f"{local_app_server}/login.html"
    home_url = f"{local_app_server}/home.html"
    plans_url = f"{local_app_server}/plans.html"
    register_url = f"{local_app_server}/register.html"

    config = AppConfig(
        instance_url=login_url,
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

    session = session_manager.create_session(login_url)
    session_id = session.session_id.value

    browser_manager = PlaywrightBrowserManager(
        session_id=session_id, config=config, event_publisher=event_bus, log_engine=log_engine
    )
    try:
        await browser_manager.initialize()
    except Exception as error:  # noqa: BLE001 — ambiente sem Chromium instalado.
        pytest.skip(f"Chromium indisponível para o teste de aceite: {error}")

    try:
        await browser_manager.open_url(login_url)

        session_manager.mark_preparing(session_id)
        session_manager.mark_waiting_authentication(session_id)
        session_manager.mark_ready(session_id)
        session_manager.start_session(session_id)

        navigation_recorder.start(session_id)

        # Mesma ligação PageChanged -> Navigation Recorder que o
        # Application Controller estabelece em produção
        # (``_on_domain_event``, ADR 0012) — aqui replicada no próprio
        # teste porque este cenário orquestra os módulos diretamente,
        # sem passar pelo Application Controller (que já tem sua
        # própria cobertura de integração).
        def _forward_navigation(event: object) -> None:
            if isinstance(event, PageChanged) and event.session_id == session_id:
                navigation_recorder.observe_navigation(tab_id=event.tab_id, url=event.url)
                navigation_recorder.capture_page()

        event_bus.subscribe(_forward_navigation)

        navigation_recorder.observe_navigation(tab_id="tab-1", url=login_url)
        navigation_recorder.capture_page()

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

        login_result = await collector.capture_current_page()
        assert login_result is not None
        assert login_result.element_count == 1  # só o link "Entrar"

        page = cast(Page, browser_manager.current_page())

        for url in (home_url, plans_url, register_url):
            await page.goto(url)
            await _wait_until_async(
                lambda expected=url: (
                    (current := navigation_recorder.get_current_page()) is not None
                    and current.url.value == expected
                )
            )
            result = await collector.capture_current_page()
            assert result is not None, f"Nenhum dado real coletado para {url}"
            assert result.element_count > 0

        pages = navigation_recorder.get_page_history()
        assert len(pages) == 4
        assert {page.url.value for page in pages} == {
            login_url,
            home_url,
            plans_url,
            register_url,
        }

        register_page = next(page for page in pages if page.url.value == register_url)
        register_elements = element_recorder.get_elements(register_page.page_id.value)
        assert {element.tag for element in register_elements} == {"input", "select", "button"}

        await collector.stop()
        navigation_recorder.stop()
        session_manager.finish_session(session_id)

        output_dir = export_engine.export(session_id)

        assert export_engine.validate(session_id) is True
        assert (output_dir / "session.json").is_file()
        assert (output_dir / "navigation.json").is_file()
        assert (output_dir / "selectors.json").is_file()
        assert (output_dir / "manifest.json").is_file()
        assert (output_dir / "report.html").is_file()

        page_files = list((output_dir / "pages").glob("*.json"))
        assert len(page_files) == 4

        screenshot_files = list((output_dir / "screenshots").glob("*.png"))
        assert screenshot_files
        for screenshot_file in screenshot_files:
            assert screenshot_file.stat().st_size > 0

        # ADR 0014/0015: os 5 comandos restantes da CLI (``status``,
        # ``validate``, ``open``, ``logs``, ``config``) rodam como
        # processos separados de ``snkb record`` (cada um via
        # ``CliRunner``, um processo novo em produção) e devem enxergar
        # a sessão gravada acima só através do que foi escrito em disco
        # — sem mais chamar ``announce_pending``.
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "local.json").write_text(
            json.dumps({"instance_url": login_url, "output_directory": "exports"}),
            encoding="utf-8",
        )
        opened_paths: list[Path] = []
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr(
            os, "startfile", lambda path: opened_paths.append(Path(path)), raising=False
        )
        monkeypatch.chdir(tmp_path)

        from snkb.presentation.cli.main import app

        runner = CliRunner()

        status_result = runner.invoke(app, ["status"])
        assert status_result.exit_code == 0
        assert str(session_id) in status_result.output

        validate_result = runner.invoke(app, ["validate"])
        assert validate_result.exit_code == 0
        assert "válida" in validate_result.output.lower()

        open_result = runner.invoke(app, ["open"])
        assert open_result.exit_code == 0
        assert len(opened_paths) == 1
        assert opened_paths[0].resolve() == output_dir.resolve()

        logs_result = runner.invoke(app, ["logs"])
        assert logs_result.exit_code == 0

        config_result = runner.invoke(app, ["config"])
        assert config_result.exit_code == 0
        assert login_url in config_result.output
    finally:
        await browser_manager.close()
