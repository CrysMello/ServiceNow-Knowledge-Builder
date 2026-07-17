"""Implementação concreta de ``ElementRecorderPort`` (Module
Specifications, Capítulo 6).

Como o Session Manager (ADR 0005) e o Navigation Recorder (ADR 0006),
não faz I/O nem importa Playwright: identifica e classifica elementos
a partir de observações brutas de DOM já coletadas por quem tem acesso
ao navegador (hoje o futuro Application Controller), via
``observe_elements()``. Nunca lê nem armazena o valor real de um campo
— a entidade ``Element`` não tem esse atributo. Ver ADR 0007 para as
decisões de design desta camada de classificação "DOM observado" →
"catálogo de elementos".
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from snkb.domain.entities.element import Element
from snkb.domain.entities.frame import Frame
from snkb.domain.enums.element_semantic_type import ElementSemanticType
from snkb.domain.enums.sensitivity_classification import SensitivityClassification
from snkb.domain.events.element_events import (
    ElementFound,
    ElementRemoved,
    ElementsCaptured,
    ElementUpdated,
    FormDetected,
    GridDetected,
    RelatedListDetected,
)
from snkb.domain.exceptions.element_exceptions import ElementNotFoundError, NoPendingElementsError
from snkb.domain.value_objects.identifiers import ElementId, FrameId, PageId

if TYPE_CHECKING:
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.domain.events.base import DomainEvent

_INPUT_TYPE_MAP: dict[str, ElementSemanticType] = {
    "password": ElementSemanticType.PASSWORD,
    "email": ElementSemanticType.EMAIL,
    "tel": ElementSemanticType.PHONE,
    "number": ElementSemanticType.NUMBER,
    "date": ElementSemanticType.DATE,
    "datetime-local": ElementSemanticType.DATETIME,
    "checkbox": ElementSemanticType.CHECKBOX,
    "radio": ElementSemanticType.RADIO_BUTTON,
}

_ROLE_MAP: dict[str, ElementSemanticType] = {
    "grid": ElementSemanticType.GRID,
    "treegrid": ElementSemanticType.GRID,
    "dialog": ElementSemanticType.DIALOG,
    "alertdialog": ElementSemanticType.DIALOG,
    "tab": ElementSemanticType.TAB,
    "menu": ElementSemanticType.MENU,
    "menuitem": ElementSemanticType.MENU,
    "checkbox": ElementSemanticType.CHECKBOX,
    "radio": ElementSemanticType.RADIO_BUTTON,
    "switch": ElementSemanticType.SWITCH,
    "combobox": ElementSemanticType.COMBOBOX,
    "button": ElementSemanticType.BUTTON,
    "link": ElementSemanticType.LINK,
}

_TAG_MAP: dict[str, ElementSemanticType] = {
    "textarea": ElementSemanticType.TEXTAREA,
    "select": ElementSemanticType.DROPDOWN,
    "button": ElementSemanticType.BUTTON,
    "a": ElementSemanticType.LINK,
    "table": ElementSemanticType.TABLE,
    "form": ElementSemanticType.FORM,
}


@dataclass(slots=True)
class RawElementObservation:
    """Atributos de DOM já lidos pelo chamador (nunca o valor do campo).

    ``parent_index`` referencia outro item do mesmo lote passado a
    ``observe_elements()`` (pré-ordem: pais antes dos filhos), não um
    ``element_id`` — o lote pode conter elementos novos que ainda não
    têm identidade.
    """

    frame_origin: str
    frame_selector: str | None
    tag: str
    role: str | None = None
    input_type: str | None = None
    semantic_type_hint: ElementSemanticType | None = None
    accessible_name: str | None = None
    label: str | None = None
    placeholder: str | None = None
    html_id: str | None = None
    name: str | None = None
    classes: tuple[str, ...] = field(default_factory=tuple)
    required: bool = False
    readonly: bool = False
    disabled: bool = False
    visible: bool = True
    enabled: bool = True
    is_sensitive_hint: bool = False
    parent_index: int | None = None


class ElementRecorder:
    """Cataloga elementos por página a partir de observações brutas de DOM
    (sem I/O próprio)."""

    def __init__(
        self,
        event_publisher: EventPublisherPort,
        log_engine: LogEnginePort,
        generate_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self._event_publisher = event_publisher
        self._log = log_engine
        self._generate_id = generate_id

        self._pending_by_page: dict[UUID, list[RawElementObservation]] = {}
        self._session_by_page: dict[UUID, UUID] = {}
        self._elements_by_id: dict[UUID, Element] = {}
        self._elements_by_page: dict[UUID, list[Element]] = {}
        self._elements_by_fingerprint: dict[tuple[UUID, str], Element] = {}
        self._frames_by_page: dict[UUID, dict[tuple[str, str | None], Frame]] = {}
        self._staged_updates: dict[UUID, RawElementObservation] = {}

    # ------------------------------------------------------------------
    # ElementRecorderPort
    # ------------------------------------------------------------------

    def capture_elements(self, page_id: UUID) -> list[Element]:
        pending = self._pending_by_page.pop(page_id, None)
        session_id = self._session_by_page.get(page_id)
        if pending is None or session_id is None:
            raise NoPendingElementsError(
                f"Nenhuma observação de elementos pendente para a página {page_id}; "
                "chame observe_elements() antes de capture_elements()."
            )

        resolved: list[Element] = []
        new_elements: list[Element] = []
        for raw in pending:
            frame = self._resolve_frame(page_id, raw.frame_origin, raw.frame_selector)
            semantic_type = raw.semantic_type_hint or self._classify(
                raw.tag, raw.input_type, raw.role
            )
            fingerprint = self._compute_fingerprint(frame.frame_id, raw)
            key = (page_id, fingerprint)

            existing = self._elements_by_fingerprint.get(key)
            if existing is not None:
                self._apply_updates(existing, raw, semantic_type)
                element = existing
                is_new = False
            else:
                element = Element(
                    element_id=ElementId(value=self._generate_id()),
                    page_id=PageId(value=page_id),
                    frame_id=frame.frame_id,
                    semantic_type=semantic_type,
                    tag=raw.tag,
                    role=raw.role,
                    accessible_name=raw.accessible_name,
                    label=raw.label,
                    placeholder=raw.placeholder,
                    html_id=raw.html_id,
                    name=raw.name,
                    classes=raw.classes,
                    required=raw.required,
                    readonly=raw.readonly,
                    disabled=raw.disabled,
                    visible=raw.visible,
                    enabled=raw.enabled,
                    fingerprint=fingerprint,
                    sensitivity_classification=self._classify_sensitivity(
                        semantic_type, raw.is_sensitive_hint
                    ),
                )
                self._elements_by_fingerprint[key] = element
                self._elements_by_id[element.element_id.value] = element
                self._elements_by_page.setdefault(page_id, []).append(element)
                is_new = True

            if raw.parent_index is not None and 0 <= raw.parent_index < len(resolved):
                element.parent_element_id = resolved[raw.parent_index].element_id

            resolved.append(element)
            if is_new:
                new_elements.append(element)

        for element in new_elements:
            self._publish(
                ElementFound(
                    session_id=session_id, page_id=page_id, element_id=element.element_id.value
                )
            )
            self._maybe_publish_detection(session_id, page_id, element)

        all_elements = self.get_elements(page_id)
        self._publish(
            ElementsCaptured(
                session_id=session_id, page_id=page_id, element_count=len(all_elements)
            )
        )
        self._log.info(
            "Elementos capturados.",
            session_id=str(session_id),
            page_id=str(page_id),
            element_count=len(all_elements),
        )
        return all_elements

    def get_elements(self, page_id: UUID) -> list[Element]:
        return list(self._elements_by_page.get(page_id, []))

    def get_element(self, element_id: UUID) -> Element | None:
        return self._elements_by_id.get(element_id)

    def find_element(self, page_id: UUID, fingerprint: str) -> Element | None:
        return self._elements_by_fingerprint.get((page_id, fingerprint))

    def update_element(self, element_id: UUID) -> Element:
        element = self._require_element(element_id)
        staged = self._staged_updates.pop(element_id, None)
        if staged is None:
            raise NoPendingElementsError(
                f"Nenhuma atualização pendente para o elemento {element_id}; "
                "chame stage_element_update() antes de update_element()."
            )
        semantic_type = staged.semantic_type_hint or self._classify(
            staged.tag, staged.input_type, staged.role
        )
        self._apply_updates(element, staged, semantic_type)

        session_id = self._session_by_page[element.page_id.value]
        self._publish(ElementUpdated(session_id=session_id, element_id=element_id))
        self._log.info("Elemento atualizado.", element_id=str(element_id))
        return element

    def remove_element(self, element_id: UUID) -> None:
        element = self._require_element(element_id)
        page_id = element.page_id.value
        session_id = self._session_by_page[page_id]

        del self._elements_by_id[element_id]
        self._elements_by_page[page_id] = [
            candidate
            for candidate in self._elements_by_page.get(page_id, [])
            if candidate.element_id.value != element_id
        ]
        if element.fingerprint is not None:
            self._elements_by_fingerprint.pop((page_id, element.fingerprint), None)
        self._staged_updates.pop(element_id, None)

        self._publish(ElementRemoved(session_id=session_id, element_id=element_id))
        self._log.info("Elemento removido.", element_id=str(element_id))

    def clear_page(self, page_id: UUID) -> None:
        for element in self._elements_by_page.pop(page_id, []):
            self._elements_by_id.pop(element.element_id.value, None)
            self._staged_updates.pop(element.element_id.value, None)
            if element.fingerprint is not None:
                self._elements_by_fingerprint.pop((page_id, element.fingerprint), None)
        self._frames_by_page.pop(page_id, None)
        self._pending_by_page.pop(page_id, None)
        self._session_by_page.pop(page_id, None)

    def get_statistics(self) -> dict[str, object]:
        by_semantic_type: dict[str, int] = {}
        by_sensitivity: dict[str, int] = {}
        for element in self._elements_by_id.values():
            semantic_key = element.semantic_type.value
            by_semantic_type[semantic_key] = by_semantic_type.get(semantic_key, 0) + 1
            sensitivity_key = element.sensitivity_classification.value
            by_sensitivity[sensitivity_key] = by_sensitivity.get(sensitivity_key, 0) + 1
        return {
            "total_elements": len(self._elements_by_id),
            "pages_with_elements": len(self._elements_by_page),
            "by_semantic_type": by_semantic_type,
            "by_sensitivity_classification": by_sensitivity,
        }

    # ------------------------------------------------------------------
    # Além da superfície mínima do Port — recebem as observações brutas
    # de DOM que quem tem acesso ao navegador já coletou; ver ADR 0007.
    # ------------------------------------------------------------------

    def observe_elements(
        self, session_id: UUID, page_id: UUID, elements: list[RawElementObservation]
    ) -> None:
        self._session_by_page[page_id] = session_id
        self._pending_by_page[page_id] = elements

    def stage_element_update(self, element_id: UUID, observation: RawElementObservation) -> None:
        self._require_element(element_id)
        self._staged_updates[element_id] = observation

    def get_frames(self, page_id: UUID) -> list[Frame]:
        return list(self._frames_by_page.get(page_id, {}).values())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_element(self, element_id: UUID) -> Element:
        element = self._elements_by_id.get(element_id)
        if element is None:
            raise ElementNotFoundError(f"Nenhum elemento capturado com o id {element_id}.")
        return element

    def _resolve_frame(self, page_id: UUID, origin: str, selector: str | None) -> Frame:
        frames = self._frames_by_page.setdefault(page_id, {})
        key = (origin, selector)
        frame = frames.get(key)
        if frame is None:
            frame = Frame(
                frame_id=FrameId(value=self._generate_id()),
                page_id=PageId(value=page_id),
                origin=origin,
                selector=selector,
            )
            frames[key] = frame
        return frame

    @staticmethod
    def _apply_updates(
        element: Element, raw: RawElementObservation, semantic_type: ElementSemanticType
    ) -> None:
        element.semantic_type = semantic_type
        element.role = raw.role
        element.accessible_name = raw.accessible_name
        element.label = raw.label
        element.placeholder = raw.placeholder
        element.html_id = raw.html_id
        element.name = raw.name
        element.classes = raw.classes
        element.required = raw.required
        element.readonly = raw.readonly
        element.disabled = raw.disabled
        element.visible = raw.visible
        element.enabled = raw.enabled
        element.sensitivity_classification = ElementRecorder._classify_sensitivity(
            semantic_type, raw.is_sensitive_hint
        )

    def _maybe_publish_detection(self, session_id: UUID, page_id: UUID, element: Element) -> None:
        element_id = element.element_id.value
        if element.semantic_type == ElementSemanticType.FORM:
            self._publish(
                FormDetected(session_id=session_id, page_id=page_id, element_id=element_id)
            )
        elif element.semantic_type == ElementSemanticType.GRID:
            self._publish(
                GridDetected(session_id=session_id, page_id=page_id, element_id=element_id)
            )
        elif element.semantic_type == ElementSemanticType.RELATED_LIST:
            self._publish(
                RelatedListDetected(session_id=session_id, page_id=page_id, element_id=element_id)
            )

    @staticmethod
    def _classify(tag: str, input_type: str | None, role: str | None) -> ElementSemanticType:
        if role is not None:
            mapped_by_role = _ROLE_MAP.get(role.lower())
            if mapped_by_role is not None:
                return mapped_by_role

        tag_lower = tag.lower()
        if tag_lower == "input":
            return _INPUT_TYPE_MAP.get((input_type or "text").lower(), ElementSemanticType.TEXTBOX)

        return _TAG_MAP.get(tag_lower, ElementSemanticType.UNKNOWN)

    @staticmethod
    def _classify_sensitivity(
        semantic_type: ElementSemanticType, is_sensitive_hint: bool
    ) -> SensitivityClassification:
        if semantic_type == ElementSemanticType.PASSWORD or is_sensitive_hint:
            return SensitivityClassification.SENSITIVE
        return SensitivityClassification.NONE

    @staticmethod
    def _compute_fingerprint(frame_id: FrameId, raw: RawElementObservation) -> str:
        parts = "|".join(
            [
                str(frame_id.value),
                raw.tag,
                raw.html_id or "",
                raw.name or "",
                raw.role or "",
                raw.accessible_name or "",
                raw.label or "",
            ]
        )
        return hashlib.sha256(parts.encode("utf-8")).hexdigest()

    def _publish(self, event: DomainEvent) -> None:
        self._event_publisher.publish(event)
