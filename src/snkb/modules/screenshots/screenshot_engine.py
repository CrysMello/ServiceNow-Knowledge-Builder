"""Implementação concreta de ``ScreenshotEnginePort`` (Module
Specifications, Capítulo 8).

Como os módulos anteriores, não faz I/O: a entidade ``Screenshot``
(``domain.entities.screenshot``) já documenta que "o conteúdo binário
em si é gravado em disco exclusivamente pelo Export Engine" — este
módulo só cataloga metadados (dimensões, tipo, nome de arquivo) de
capturas já realizadas por quem tem acesso ao navegador (hoje o futuro
Application Controller, via Playwright assíncrono), recebidas através
de ``stage_capture()``. Ver ADR 0009 para as decisões de design,
incluindo a conexão com ``CapturePolicyModel``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from snkb.domain.entities.screenshot import Screenshot
from snkb.domain.enums.screenshot_type import ScreenshotType
from snkb.domain.events.screenshot_events import (
    ScreenshotCreated,
    ScreenshotFailed,
    ScreenshotSkipped,
)
from snkb.domain.exceptions.screenshot_exceptions import (
    NoPendingCaptureError,
    ScreenshotCaptureError,
    ScreenshotNotFoundError,
)
from snkb.domain.value_objects.identifiers import PageId, ScreenshotId, SessionId

if TYPE_CHECKING:
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.domain.events.base import DomainEvent
    from snkb.shared.dtos.app_config import CapturePolicyModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class RawScreenshotObservation:
    """Dimensões de uma captura já realizada por quem tem acesso ao
    navegador. Nunca carrega os bytes da imagem — só o suficiente para
    catalogar e validar estruturalmente a evidência."""

    width: int
    height: int
    byte_size: int | None = None


class ScreenshotEngine:
    """Cataloga metadados de screenshots já capturadas, sem nunca tocar o
    conteúdo binário."""

    def __init__(
        self,
        event_publisher: EventPublisherPort,
        log_engine: LogEnginePort,
        capture_policy: CapturePolicyModel,
        now: Callable[[], datetime] = _utcnow,
        generate_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self._event_publisher = event_publisher
        self._log = log_engine
        self._capture_policy = capture_policy
        self._now = now
        self._generate_id = generate_id

        self._pending: dict[tuple[UUID, ScreenshotType], RawScreenshotObservation] = {}
        self._session_by_page: dict[UUID, UUID] = {}
        self._screenshots_by_id: dict[UUID, Screenshot] = {}
        self._screenshots_by_page: dict[UUID, list[Screenshot]] = {}
        self._byte_size_by_id: dict[UUID, int | None] = {}
        self._sequence_by_page: dict[UUID, int] = {}

    # ------------------------------------------------------------------
    # ScreenshotEnginePort
    # ------------------------------------------------------------------

    def capture(self, page_id: UUID, capture_type: ScreenshotType) -> Screenshot:
        session_id = self._session_by_page.get(page_id)

        if not self._capture_policy.capture_screenshots:
            if session_id is not None:
                self._publish(
                    ScreenshotSkipped(
                        session_id=session_id,
                        page_id=page_id,
                        reason="Captura de screenshots desabilitada na política de configuração.",
                    )
                )
            raise NoPendingCaptureError(
                "A política de configuração desabilita a captura de screenshots "
                "(capture_policy.capture_screenshots=False)."
            )

        observation = self._pending.pop((page_id, capture_type), None)
        if observation is None or session_id is None:
            raise NoPendingCaptureError(
                f"Nenhuma captura pendente para a página {page_id} ({capture_type.value}); "
                "chame stage_capture() antes de capture()."
            )

        if observation.width <= 0 or observation.height <= 0:
            self._publish(
                ScreenshotFailed(
                    session_id=session_id,
                    page_id=page_id,
                    reason=f"Dimensões inválidas: {observation.width}x{observation.height}.",
                )
            )
            raise ScreenshotCaptureError(
                f"Dimensões inválidas para a captura: {observation.width}x{observation.height}."
            )

        screenshot_id = self._generate_id()
        sequence = self._sequence_by_page.get(page_id, 0) + 1
        self._sequence_by_page[page_id] = sequence
        file_name = f"{page_id}_{capture_type.value}_{sequence:03d}.png"

        screenshot = Screenshot(
            screenshot_id=ScreenshotId(value=screenshot_id),
            session_id=SessionId(value=session_id),
            page_id=PageId(value=page_id),
            captured_at=self._now(),
            capture_type=capture_type,
            file_name=file_name,
            width=observation.width,
            height=observation.height,
        )
        self._screenshots_by_id[screenshot_id] = screenshot
        self._screenshots_by_page.setdefault(page_id, []).append(screenshot)
        self._byte_size_by_id[screenshot_id] = observation.byte_size

        self._publish(
            ScreenshotCreated(
                session_id=session_id,
                page_id=page_id,
                screenshot_id=screenshot_id,
                file_name=file_name,
            )
        )
        self._log.info(
            "Screenshot capturado.", page_id=str(page_id), screenshot_id=str(screenshot_id)
        )
        return screenshot

    def capture_page(self, page_id: UUID) -> Screenshot:
        capture_type = (
            ScreenshotType.FULL_PAGE
            if self._capture_policy.full_page_screenshots
            else ScreenshotType.VIEWPORT
        )
        return self.capture(page_id, capture_type)

    def capture_modal(self, page_id: UUID) -> Screenshot:
        return self.capture(page_id, ScreenshotType.MODAL)

    def capture_popup(self, page_id: UUID) -> Screenshot:
        return self.capture(page_id, ScreenshotType.POPUP)

    def validate(self, screenshot_id: UUID) -> bool:
        screenshot = self._screenshots_by_id.get(screenshot_id)
        if screenshot is None:
            return False
        if screenshot.width <= 0 or screenshot.height <= 0:
            return False
        byte_size = self._byte_size_by_id.get(screenshot_id)
        return not (byte_size is not None and byte_size <= 0)

    def get_screenshot(self, screenshot_id: UUID) -> Screenshot | None:
        return self._screenshots_by_id.get(screenshot_id)

    def get_screenshots(self, page_id: UUID) -> list[Screenshot]:
        """Além da superfície mínima do Port — usado pelo Export Engine
        (ADR 0010) para montar o manifesto de screenshots por página,
        já que o Port só expõe consulta por ``screenshot_id`` isolado."""
        return list(self._screenshots_by_page.get(page_id, []))

    def delete(self, screenshot_id: UUID) -> None:
        screenshot = self._screenshots_by_id.pop(screenshot_id, None)
        if screenshot is None:
            raise ScreenshotNotFoundError(f"Nenhum screenshot capturado com o id {screenshot_id}.")
        page_id = screenshot.page_id.value
        self._screenshots_by_page[page_id] = [
            candidate
            for candidate in self._screenshots_by_page.get(page_id, [])
            if candidate.screenshot_id.value != screenshot_id
        ]
        self._byte_size_by_id.pop(screenshot_id, None)
        self._log.info("Screenshot removido.", screenshot_id=str(screenshot_id))

    def clear(self, page_id: UUID) -> None:
        for screenshot in self._screenshots_by_page.pop(page_id, []):
            self._screenshots_by_id.pop(screenshot.screenshot_id.value, None)
            self._byte_size_by_id.pop(screenshot.screenshot_id.value, None)
        self._sequence_by_page.pop(page_id, None)
        self._session_by_page.pop(page_id, None)
        self._pending = {
            key: observation for key, observation in self._pending.items() if key[0] != page_id
        }

    def statistics(self) -> dict[str, object]:
        by_type: dict[str, int] = {}
        for screenshot in self._screenshots_by_id.values():
            key = screenshot.capture_type.value
            by_type[key] = by_type.get(key, 0) + 1
        return {
            "total_screenshots": len(self._screenshots_by_id),
            "pages_with_screenshots": len(self._screenshots_by_page),
            "by_capture_type": by_type,
        }

    # ------------------------------------------------------------------
    # Além da superfície mínima do Port — necessário porque nenhum
    # método do Port recebe dimensões ou ``session_id``; ver ADR 0009.
    # ------------------------------------------------------------------

    def stage_capture(
        self,
        session_id: UUID,
        page_id: UUID,
        capture_type: ScreenshotType,
        observation: RawScreenshotObservation,
    ) -> None:
        self._session_by_page[page_id] = session_id
        self._pending[(page_id, capture_type)] = observation

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _publish(self, event: DomainEvent) -> None:
        self._event_publisher.publish(event)
