"""Structural contract tests: each port must expose exactly the public
methods documented in its Module Specification chapter. These tests
guard against silent drift once concrete adapters are implemented.
"""

from __future__ import annotations

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
from snkb.application.services.application_controller_port import ApplicationControllerPort


def _public_methods(protocol: type) -> set[str]:
    return {name for name in vars(protocol) if not name.startswith("_")}


def test_browser_manager_port_matches_module_specification_3_14() -> None:
    assert _public_methods(BrowserManagerPort) == {
        "initialize",
        "shutdown",
        "open_url",
        "current_page",
        "current_context",
        "browser_status",
        "current_tabs",
        "wait_login",
        "is_alive",
        "restart",
        "close",
    }


def test_session_manager_port_matches_module_specification_4_16() -> None:
    assert _public_methods(SessionManagerPort) == {
        "create_session",
        "start_session",
        "pause_session",
        "resume_session",
        "finish_session",
        "cancel_session",
        "get_session",
        "get_statistics",
        "update_metadata",
        "is_active",
    }


def test_navigation_recorder_port_matches_module_specification_5_17() -> None:
    assert _public_methods(NavigationRecorderPort) == {
        "start",
        "stop",
        "capture_page",
        "update_page",
        "close_page",
        "get_current_page",
        "get_navigation_graph",
        "get_page_history",
        "export_navigation",
        "clear_navigation",
    }


def test_element_recorder_port_matches_module_specification_6_18() -> None:
    assert _public_methods(ElementRecorderPort) == {
        "capture_elements",
        "get_elements",
        "get_element",
        "find_element",
        "update_element",
        "remove_element",
        "clear_page",
        "get_statistics",
    }


def test_selector_analyzer_port_matches_module_specification_7_17() -> None:
    assert _public_methods(SelectorAnalyzerPort) == {
        "analyze",
        "generate",
        "calculate_score",
        "get_best_selector",
        "get_all_selectors",
        "validate_selector",
        "update_selector",
        "remove_selector",
    }


def test_screenshot_engine_port_matches_module_specification_8_17() -> None:
    assert _public_methods(ScreenshotEnginePort) == {
        "capture",
        "capture_page",
        "capture_modal",
        "capture_popup",
        "validate",
        "get_screenshot",
        "delete",
        "clear",
        "statistics",
    }


def test_export_engine_port_matches_module_specification_9_14() -> None:
    assert _public_methods(ExportEnginePort) == {
        "export",
        "export_session",
        "export_navigation",
        "export_pages",
        "export_selectors",
        "export_statistics",
        "export_manifest",
        "generate_report",
        "validate",
        "clear_temp",
    }


def test_log_engine_port_matches_module_specification_10_15() -> None:
    assert _public_methods(LogEnginePort) == {
        "trace",
        "debug",
        "info",
        "warning",
        "error",
        "critical",
        "exception",
        "flush",
        "export",
        "statistics",
    }


def test_event_publisher_port_exposes_publish_only() -> None:
    assert _public_methods(EventPublisherPort) == {"publish"}


def test_application_controller_port_matches_module_specification_2_5() -> None:
    assert _public_methods(ApplicationControllerPort) == {"dispatch", "query", "subscribe"}


def test_browser_data_collector_port_matches_adr_0013() -> None:
    assert _public_methods(BrowserDataCollectorPort) == {
        "start",
        "capture_current_page",
        "stop",
    }
