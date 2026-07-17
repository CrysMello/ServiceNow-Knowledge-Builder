"""Implementação concreta de ``ExportEnginePort`` (Module Specifications,
Capítulo 9).

Diferente de todos os módulos anteriores, este realmente grava
arquivos em disco — é o único papel deste módulo ("Consolidates data
produced by every other module into the on-disk Knowledge Base. Never
captures data itself", 9.4). Usa apenas a biblioteca padrão
(``pathlib``, ``json`` via Pydantic, ``hashlib``, ``html``) para isso,
nunca Playwright. Ver ADR 0010 para as decisões de design, incluindo
por que este é o primeiro módulo central com I/O real de arquivo.
"""

from __future__ import annotations

import hashlib
import html
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from snkb.domain.events.export_events import (
    ExportCompleted,
    ExportFailed,
    ExportProgress,
    ExportStarted,
    ReportCreated,
)
from snkb.domain.exceptions.export_exceptions import ExportValidationError
from snkb.shared.dtos.manifest_json import ManifestFileEntryModel, ManifestJsonModel
from snkb.shared.dtos.navigation_json import NavigationJsonModel
from snkb.shared.dtos.page_json import ElementModel, FrameModel, PageJsonModel
from snkb.shared.dtos.screenshots_json import ScreenshotMetadataModel, ScreenshotsJsonModel
from snkb.shared.dtos.selectors_json import (
    ElementSelectorsModel,
    SelectorCandidateModel,
    SelectorsJsonModel,
)
from snkb.shared.dtos.session_json import ScreenResolutionModel, SessionJsonModel, ViewportModel
from snkb.shared.dtos.statistics_json import StatisticsJsonModel

if TYPE_CHECKING:
    from pydantic import BaseModel

    from snkb.application.ports.element_recorder_port import ElementRecorderPort
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.application.ports.navigation_recorder_port import NavigationRecorderPort
    from snkb.application.ports.screenshot_engine_port import ScreenshotEnginePort
    from snkb.application.ports.selector_analyzer_port import SelectorAnalyzerPort
    from snkb.application.ports.session_manager_port import SessionManagerPort
    from snkb.domain.entities.element import Element
    from snkb.domain.entities.frame import Frame
    from snkb.domain.entities.screenshot import Screenshot
    from snkb.domain.entities.selector import ElementSelectors
    from snkb.domain.entities.session import Session
    from snkb.domain.events.base import DomainEvent
    from snkb.domain.value_objects.selector_candidate import SelectorCandidate

    class _ElementRecorderWithFrames(ElementRecorderPort, Protocol):
        def get_frames(self, page_id: UUID) -> list[Frame]: ...

    class _ScreenshotEngineWithPageQuery(ScreenshotEnginePort, Protocol):
        def get_screenshots(self, page_id: UUID) -> list[Screenshot]: ...


_SCHEMA_VERSION = "1.0"
_CONTENT_TYPES = {
    ".json": "application/json",
    ".png": "image/png",
    ".html": "text/html",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ExportEngine:
    """Consolida os dados já produzidos pelos demais módulos centrais em
    um diretório exclusivo por sessão (RN-005), sem nunca capturar nada
    sozinho."""

    def __init__(
        self,
        session_manager: SessionManagerPort,
        navigation_recorder: NavigationRecorderPort,
        element_recorder: _ElementRecorderWithFrames,
        selector_analyzer: SelectorAnalyzerPort,
        screenshot_engine: _ScreenshotEngineWithPageQuery,
        event_publisher: EventPublisherPort,
        log_engine: LogEnginePort,
        output_directory: Path,
        now: Callable[[], datetime] = _utcnow,
        screenshot_bytes_provider: Callable[[UUID], bytes | None] | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._navigation_recorder = navigation_recorder
        self._element_recorder = element_recorder
        self._selector_analyzer = selector_analyzer
        self._screenshot_engine = screenshot_engine
        self._event_publisher = event_publisher
        self._log = log_engine
        self._output_directory = output_directory
        self._now = now
        self._screenshot_bytes_provider = screenshot_bytes_provider

    # ------------------------------------------------------------------
    # ExportEnginePort
    # ------------------------------------------------------------------

    def export(self, session_id: UUID) -> Path:
        self._publish(ExportStarted(session_id=session_id))
        try:
            self.export_session(session_id)
            self._publish(ExportProgress(session_id=session_id, step="session", percentage=15))
            self.export_navigation(session_id)
            self._publish(ExportProgress(session_id=session_id, step="navigation", percentage=30))
            self.export_pages(session_id)
            self._publish(ExportProgress(session_id=session_id, step="pages", percentage=50))
            self.export_selectors(session_id)
            self._publish(ExportProgress(session_id=session_id, step="selectors", percentage=65))
            self.export_statistics(session_id)
            self._publish(ExportProgress(session_id=session_id, step="statistics", percentage=80))
            self.generate_report(session_id)
            self._publish(ExportProgress(session_id=session_id, step="report", percentage=90))
            manifest_path = self.export_manifest(session_id)
            self._publish(ExportProgress(session_id=session_id, step="manifest", percentage=100))
        except Exception as error:
            self._publish(ExportFailed(session_id=session_id, reason=str(error)))
            raise

        output_dir = manifest_path.parent
        self._publish(ExportCompleted(session_id=session_id, output_directory=str(output_dir)))
        self._log.info(
            "Exportação concluída.", session_id=str(session_id), output_directory=str(output_dir)
        )
        return output_dir

    def export_session(self, session_id: UUID) -> Path:
        session = self._session_manager.get_session(session_id)
        model = self._build_session_model(session)
        return self._write_json_model(session_id, "session.json", model)

    def export_navigation(self, session_id: UUID) -> Path:
        data = self._navigation_recorder.export_navigation()
        self._verify_session_match(session_id, data.get("session_id"))
        model = NavigationJsonModel.model_validate(data)
        return self._write_json_model(session_id, "navigation.json", model)

    def export_pages(self, session_id: UUID) -> list[Path]:
        written: list[Path] = []
        for page in self._navigation_recorder.get_page_history():
            page_id = page.page_id.value
            elements = self._element_recorder.get_elements(page_id)
            frames = self._element_recorder.get_frames(page_id)
            screenshots = self._screenshot_engine.get_screenshots(page_id)

            element_models = [
                self._build_element_model(
                    element, self._selector_analyzer.get_all_selectors(element.element_id.value)
                )
                for element in elements
            ]
            frame_models = [
                FrameModel(
                    frame_id=frame.frame_id.value,
                    origin=frame.origin,
                    selector=frame.selector,
                    parent_frame_id=(
                        frame.parent_frame_id.value if frame.parent_frame_id is not None else None
                    ),
                )
                for frame in frames
            ]
            page_model = PageJsonModel(
                schema_version=_SCHEMA_VERSION,
                page_id=page_id,
                revision_id=page.revision_id,
                name_original=page.name_original,
                name_reviewed=page.name_reviewed,
                title=page.title,
                url_sanitized=page.url.value,
                route=page.route,
                frame_tree=frame_models,
                fingerprint=page.fingerprint,
                first_seen=page.first_seen,
                last_seen=page.last_seen,
                parent_context=page.parent_context,
                elements=element_models,
                screenshots=[screenshot.screenshot_id.value for screenshot in screenshots],
                limitations=list(page.limitations),
            )
            written.append(self._write_json_model(session_id, f"pages/{page_id}.json", page_model))

            if screenshots:
                screenshots_model = ScreenshotsJsonModel(
                    schema_version=_SCHEMA_VERSION,
                    session_id=session_id,
                    page_id=page_id,
                    screenshots=[
                        ScreenshotMetadataModel(
                            id=screenshot.screenshot_id.value,
                            file=screenshot.file_name,
                            type=screenshot.capture_type.value,
                            timestamp=screenshot.captured_at,
                            width=screenshot.width,
                            height=screenshot.height,
                        )
                        for screenshot in screenshots
                    ],
                )
                self._write_json_model(session_id, f"screenshots/{page_id}.json", screenshots_model)
                self._write_screenshot_files(session_id, screenshots)

        return written

    def export_selectors(self, session_id: UUID) -> Path:
        element_models: list[ElementSelectorsModel] = []
        for page in self._navigation_recorder.get_page_history():
            for element in self._element_recorder.get_elements(page.page_id.value):
                selectors = self._selector_analyzer.get_all_selectors(element.element_id.value)
                best = selectors.best_candidate
                fallback = [
                    candidate for candidate in selectors.candidates if candidate is not best
                ]
                element_models.append(
                    ElementSelectorsModel(
                        page_id=page.page_id.value,
                        element_id=element.element_id.value,
                        best_strategy=self._candidate_model(best) if best is not None else None,
                        fallback_strategies=[self._candidate_model(c) for c in fallback],
                    )
                )
        model = SelectorsJsonModel(
            schema_version=_SCHEMA_VERSION, session_id=session_id, elements=element_models
        )
        return self._write_json_model(session_id, "selectors.json", model)

    def export_statistics(self, session_id: UUID) -> Path:
        session = self._session_manager.get_session(session_id)
        element_stats = self._element_recorder.get_statistics()
        screenshot_stats = self._screenshot_engine.statistics()
        pages = self._navigation_recorder.get_page_history()
        total_selectors = sum(
            len(self._selector_analyzer.get_all_selectors(element.element_id.value).candidates)
            for page in pages
            for element in self._element_recorder.get_elements(page.page_id.value)
        )
        model = StatisticsJsonModel(
            schema_version=_SCHEMA_VERSION,
            session_id=session_id,
            total_pages=len(pages),
            total_elements=cast(int, element_stats.get("total_elements", 0)),
            total_selectors=total_selectors,
            total_screenshots=cast(int, screenshot_stats.get("total_screenshots", 0)),
            total_events=0,
            total_logs=0,
            capture_duration_seconds=session.duration_seconds,
            export_duration_seconds=None,
            error_count=0,
            warning_count=len(session.warnings),
        )
        return self._write_json_model(session_id, "statistics.json", model)

    def export_manifest(self, session_id: UUID) -> Path:
        output_dir = self._session_output_dir(session_id)
        entries: list[ManifestFileEntryModel] = []
        if output_dir.is_dir():
            for file_path in sorted(output_dir.rglob("*")):
                if not file_path.is_file() or file_path.suffix == ".tmp":
                    continue
                data = file_path.read_bytes()
                entries.append(
                    ManifestFileEntryModel(
                        path=file_path.relative_to(output_dir).as_posix(),
                        size_bytes=len(data),
                        sha256=hashlib.sha256(data).hexdigest(),
                        content_type=self._content_type_for(file_path),
                    )
                )
        model = ManifestJsonModel(
            schema_version=_SCHEMA_VERSION,
            session_id=session_id,
            generator="ServiceNow Knowledge Builder",
            created_at=self._now(),
            files=entries,
        )
        return self._write_json_model(session_id, "manifest.json", model)

    def generate_report(self, session_id: UUID) -> Path:
        session = self._session_manager.get_session(session_id)
        pages = self._navigation_recorder.get_page_history()
        rows = "\n".join(
            f"<tr><td>{html.escape(page.title)}</td><td>{html.escape(page.url.value)}</td><td>{len(self._element_recorder.get_elements(page.page_id.value))}</td></tr>"
            for page in pages
        )
        content = (
            "<!doctype html>\n"
            '<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
            f"<title>Relatório da sessão {html.escape(str(session_id))}</title>\n</head>\n<body>\n"
            "<h1>ServiceNow Knowledge Builder — Relatório da sessão</h1>\n"
            f"<p>Instância: {html.escape(session.instance_url)}</p>\n"
            f"<p>Status: {html.escape(session.status.value)}</p>\n"
            f"<p>Total de páginas: {len(pages)}</p>\n"
            '<table border="1">\n<thead><tr><th>Página</th><th>URL</th>'
            f"<th>Elementos</th></tr></thead>\n<tbody>\n{rows}\n</tbody>\n</table>\n"
            "</body>\n</html>\n"
        )
        output_dir = self._session_output_dir(session_id)
        target = output_dir / "report.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_name(target.name + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(target)

        self._publish(ReportCreated(session_id=session_id, report_path=str(target)))
        self._log.info(
            "Relatório HTML gerado.", session_id=str(session_id), report_path=str(target)
        )
        return target

    def validate(self, session_id: UUID) -> bool:
        output_dir = self._session_output_dir(session_id)
        try:
            SessionJsonModel.model_validate_json(self._read(output_dir / "session.json"))
            NavigationJsonModel.model_validate_json(self._read(output_dir / "navigation.json"))
            SelectorsJsonModel.model_validate_json(self._read(output_dir / "selectors.json"))
            StatisticsJsonModel.model_validate_json(self._read(output_dir / "statistics.json"))
            manifest = ManifestJsonModel.model_validate_json(
                self._read(output_dir / "manifest.json")
            )
            for page_file in sorted((output_dir / "pages").glob("*.json")):
                PageJsonModel.model_validate_json(page_file.read_text(encoding="utf-8"))
            for entry in manifest.files:
                file_path = output_dir / entry.path
                if not file_path.is_file():
                    return False
                if hashlib.sha256(file_path.read_bytes()).hexdigest() != entry.sha256:
                    return False
        except (OSError, ValueError) as error:
            self._log.warning(
                f"Validação de exportação falhou: {error}", session_id=str(session_id)
            )
            return False
        return True

    def clear_temp(self, session_id: UUID) -> None:
        output_dir = self._session_output_dir(session_id)
        if not output_dir.is_dir():
            return
        for tmp_file in output_dir.rglob("*.tmp"):
            tmp_file.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_session_model(self, session: Session) -> SessionJsonModel:
        if (
            session.recording_start is None
            or session.browser is None
            or session.browser_version is None
            or session.operating_system is None
            or session.screen_resolution is None
            or session.viewport is None
        ):
            raise ExportValidationError(
                f"Sessão {session.session_id} não tem metadados obrigatórios para exportação "
                "(recording_start/browser/browser_version/operating_system/screen_resolution/"
                "viewport). Colete os metadados do navegador via SessionManager.update_metadata() "
                "antes de exportar."
            )
        return SessionJsonModel(
            schema_version=_SCHEMA_VERSION,
            recording_id=session.session_id.value,
            instance_url=session.instance_url,
            instance_name=session.instance_name,
            home_title=session.home_title,
            recording_start=session.recording_start,
            recording_end=session.recording_end,
            duration_seconds=session.duration_seconds,
            status=session.status.value,
            service_now_version=session.service_now_version,
            service_now_version_source=session.service_now_version_source,
            language=session.language,
            locale=session.locale,
            timezone=session.timezone,
            browser=session.browser,
            browser_version=session.browser_version,
            operating_system=session.operating_system,
            screen_resolution=ScreenResolutionModel(
                width=session.screen_resolution.width, height=session.screen_resolution.height
            ),
            viewport=ViewportModel(width=session.viewport.width, height=session.viewport.height),
            device_scale_factor=session.device_scale_factor,
            zoom=session.zoom,
            theme=session.theme,
            authenticated_user=session.authenticated_user,
            warnings=list(session.warnings),
        )

    def _build_element_model(self, element: Element, selectors: ElementSelectors) -> ElementModel:
        return ElementModel(
            element_id=element.element_id.value,
            page_id=element.page_id.value,
            frame_id=element.frame_id.value,
            semantic_type=element.semantic_type.value,
            tag=element.tag,
            role=element.role,
            accessible_name=element.accessible_name,
            label=element.label,
            placeholder=element.placeholder,
            html_id=element.html_id,
            name=element.name,
            classes=list(element.classes),
            required=element.required,
            readonly=element.readonly,
            disabled=element.disabled,
            visible=element.visible,
            enabled=element.enabled,
            fingerprint=element.fingerprint,
            sensitivity_classification=element.sensitivity_classification.value,
            selectors=[
                self._candidate_model(candidate).model_dump(mode="json")
                for candidate in selectors.candidates
            ],
        )

    @staticmethod
    def _candidate_model(candidate: SelectorCandidate) -> SelectorCandidateModel:
        return SelectorCandidateModel(
            strategy=candidate.strategy.value,
            value=candidate.value,
            uniqueness_count=candidate.uniqueness_count,
            confidence_score=candidate.confidence_score,
            stability_score=candidate.stability_score,
            validated_at=candidate.validated_at,
            notes=candidate.notes,
        )

    def _write_screenshot_files(self, session_id: UUID, screenshots: list[Screenshot]) -> None:
        if self._screenshot_bytes_provider is None:
            return
        output_dir = self._session_output_dir(session_id)
        for screenshot in screenshots:
            data = self._screenshot_bytes_provider(screenshot.screenshot_id.value)
            if data is None:
                continue
            target = output_dir / "screenshots" / screenshot.file_name
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = target.with_name(target.name + ".tmp")
            tmp_path.write_bytes(data)
            tmp_path.replace(target)

    def _write_json_model(self, session_id: UUID, relative_path: str, model: BaseModel) -> Path:
        output_dir = self._session_output_dir(session_id)
        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_name(target.name + ".tmp")
        tmp_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(target)
        return target

    def _session_output_dir(self, session_id: UUID) -> Path:
        return self._output_directory / str(session_id)

    @staticmethod
    def _verify_session_match(expected: UUID, actual: object) -> None:
        if str(actual) != str(expected):
            raise ExportValidationError(
                f"A sessão ativa no Navigation Recorder ({actual!r}) não corresponde "
                f"à sessão solicitada para exportação ({expected})."
            )

    @staticmethod
    def _content_type_for(path: Path) -> str:
        return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _publish(self, event: DomainEvent) -> None:
        self._event_publisher.publish(event)
