"""Implementação concreta de ``SelectorAnalyzerPort`` (Module
Specifications, Capítulo 7).

Diferente dos módulos anteriores, este não precisa de nenhuma
observação bruta externa: todos os atributos necessários (``html_id``,
``name``, ``accessible_name``, ``role``, ``tag``, ``classes``,
``parent_element_id``) já foram capturados e classificados pelo
Element Recorder (ADR 0007). Por isso a única dependência de outro
módulo central é ``ElementRecorderPort`` (7.5) — sem I/O, sem
Playwright, sem nenhum acesso ao navegador real. Ver ADR 0008 para as
decisões de design da geração e pontuação de seletores.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from snkb.domain.entities.selector import ElementSelectors
from snkb.domain.enums.selector_strategy_type import SelectorStrategyType
from snkb.domain.events.selector_events import (
    LowConfidenceSelector,
    SelectorConflict,
    SelectorRemoved,
    SelectorsReady,
    SelectorUpdated,
)
from snkb.domain.exceptions.element_exceptions import ElementNotFoundError
from snkb.domain.exceptions.selector_exceptions import (
    NoViableSelectorError,
    PageSessionNotRegisteredError,
)
from snkb.domain.value_objects.identifiers import ElementId
from snkb.domain.value_objects.selector_candidate import SelectorCandidate

if TYPE_CHECKING:
    from snkb.application.ports.element_recorder_port import ElementRecorderPort
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.domain.entities.element import Element
    from snkb.domain.events.base import DomainEvent

_STRATEGY_PRIORITY_WEIGHT: dict[SelectorStrategyType, int] = {
    SelectorStrategyType.ID: 100,
    SelectorStrategyType.DATA_TESTID: 90,
    SelectorStrategyType.NAME: 80,
    SelectorStrategyType.ARIA_LABEL: 70,
    SelectorStrategyType.ROLE: 60,
    SelectorStrategyType.CSS: 50,
    SelectorStrategyType.XPATH_RELATIVE: 30,
    SelectorStrategyType.XPATH_ABSOLUTE: 10,
}

_LOW_CONFIDENCE_THRESHOLD = 50
_MAX_XPATH_DEPTH = 50


class SelectorAnalyzer:
    """Gera, pontua e cataloga estratégias de localização a partir de
    elementos já capturados pelo Element Recorder."""

    def __init__(
        self,
        element_recorder: ElementRecorderPort,
        event_publisher: EventPublisherPort,
        log_engine: LogEnginePort,
    ) -> None:
        self._element_recorder = element_recorder
        self._event_publisher = event_publisher
        self._log = log_engine

        self._selectors_by_element: dict[UUID, ElementSelectors] = {}
        self._session_by_page: dict[UUID, UUID] = {}

    # ------------------------------------------------------------------
    # SelectorAnalyzerPort
    # ------------------------------------------------------------------

    def analyze(self, element_id: UUID) -> ElementSelectors:
        element = self._require_element(element_id)
        candidates = self.generate(element_id)
        if not candidates:
            raise NoViableSelectorError(
                f"Nenhuma estratégia de seleção pôde ser gerada para o elemento {element_id}."
            )

        selectors = ElementSelectors(element_id=ElementId(value=element_id), candidates=candidates)
        self._selectors_by_element[element_id] = selectors

        session_id = self._session_for_page(element.page_id.value)
        self._publish(SelectorsReady(session_id=session_id, element_id=element_id))

        best = candidates[0]
        if self.calculate_score(best) < _LOW_CONFIDENCE_THRESHOLD:
            self._publish(
                LowConfidenceSelector(
                    session_id=session_id,
                    element_id=element_id,
                    confidence_score=best.confidence_score,
                )
            )

        id_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.strategy == SelectorStrategyType.ID
            ),
            None,
        )
        if id_candidate is not None and (id_candidate.uniqueness_count or 0) > 1:
            self._publish(
                SelectorConflict(
                    session_id=session_id,
                    element_id=element_id,
                    reason=(
                        f"O id {element.html_id!r} não é único na página "
                        f"({id_candidate.uniqueness_count} ocorrências)."
                    ),
                )
            )

        self._log.info("Seletores analisados.", element_id=str(element_id))
        return selectors

    def generate(self, element_id: UUID) -> list[SelectorCandidate]:
        element = self._require_element(element_id)
        siblings = self._element_recorder.get_elements(element.page_id.value)

        candidates: list[SelectorCandidate] = []

        if element.html_id:
            count = sum(1 for other in siblings if other.html_id == element.html_id)
            candidates.append(
                SelectorCandidate(
                    strategy=SelectorStrategyType.ID,
                    value=f"#{element.html_id}",
                    confidence_score=95 if count == 1 else 40,
                    stability_score=80,
                    uniqueness_count=count,
                )
            )

        if element.name:
            count = sum(1 for other in siblings if other.name == element.name)
            candidates.append(
                SelectorCandidate(
                    strategy=SelectorStrategyType.NAME,
                    value=f'[name="{element.name}"]',
                    confidence_score=85 if count == 1 else 45,
                    stability_score=75,
                    uniqueness_count=count,
                )
            )

        aria_label = element.accessible_name or element.label
        if aria_label:
            count = sum(
                1 for other in siblings if (other.accessible_name or other.label) == aria_label
            )
            candidates.append(
                SelectorCandidate(
                    strategy=SelectorStrategyType.ARIA_LABEL,
                    value=f'[aria-label="{aria_label}"]',
                    confidence_score=75 if count == 1 else 35,
                    stability_score=65,
                    uniqueness_count=count,
                )
            )

        if element.role:
            count = sum(1 for other in siblings if other.role == element.role)
            candidates.append(
                SelectorCandidate(
                    strategy=SelectorStrategyType.ROLE,
                    value=f'[role="{element.role}"]',
                    confidence_score=60 if count == 1 else 25,
                    stability_score=55,
                    uniqueness_count=count,
                )
            )

        candidates.append(
            SelectorCandidate(
                strategy=SelectorStrategyType.CSS,
                value=self._build_css_selector(element),
                confidence_score=50 if (element.html_id or element.classes) else 20,
                stability_score=50,
            )
        )
        candidates.append(
            SelectorCandidate(
                strategy=SelectorStrategyType.XPATH_RELATIVE,
                value=self._build_relative_xpath(element),
                confidence_score=30,
                stability_score=30,
            )
        )
        candidates.append(
            SelectorCandidate(
                strategy=SelectorStrategyType.XPATH_ABSOLUTE,
                value=self._build_absolute_xpath(element),
                confidence_score=15,
                stability_score=10,
            )
        )

        candidates.sort(key=self.calculate_score, reverse=True)
        return candidates

    def calculate_score(self, candidate: SelectorCandidate) -> int:
        weight = _STRATEGY_PRIORITY_WEIGHT[candidate.strategy]
        combined = weight * 0.4 + candidate.confidence_score * 0.4 + candidate.stability_score * 0.2
        return max(0, min(100, round(combined)))

    def get_best_selector(self, element_id: UUID) -> SelectorCandidate | None:
        candidates = self.get_all_selectors(element_id).candidates
        return candidates[0] if candidates else None

    def get_all_selectors(self, element_id: UUID) -> ElementSelectors:
        cached = self._selectors_by_element.get(element_id)
        if cached is not None:
            return cached
        return self.analyze(element_id)

    def validate_selector(self, element_id: UUID, candidate: SelectorCandidate) -> bool:
        element = self._element_recorder.get_element(element_id)
        if element is None or not candidate.value.strip():
            return False
        if candidate.strategy == SelectorStrategyType.ID:
            return element.html_id is not None and candidate.value == f"#{element.html_id}"
        if candidate.strategy == SelectorStrategyType.NAME:
            return element.name is not None and element.name in candidate.value
        if candidate.strategy == SelectorStrategyType.ARIA_LABEL:
            return bool(element.accessible_name or element.label)
        if candidate.strategy == SelectorStrategyType.ROLE:
            return element.role is not None and element.role in candidate.value
        # CSS/XPATH_RELATIVE/XPATH_ABSOLUTE/DATA_TESTID: sem DOM real para
        # verificar unicidade, só validação estrutural (valor não vazio).
        return True

    def update_selector(self, element_id: UUID) -> ElementSelectors:
        selectors = self.analyze(element_id)
        element = self._require_element(element_id)
        session_id = self._session_for_page(element.page_id.value)
        self._publish(SelectorUpdated(session_id=session_id, element_id=element_id))
        return selectors

    def remove_selector(self, element_id: UUID, strategy: str) -> None:
        selectors = self._selectors_by_element.get(element_id)
        if selectors is None:
            raise ElementNotFoundError(
                f"Nenhum seletor foi analisado para o elemento {element_id}."
            )
        selectors.candidates = [
            candidate for candidate in selectors.candidates if candidate.strategy.value != strategy
        ]
        element = self._require_element(element_id)
        session_id = self._session_for_page(element.page_id.value)
        self._publish(SelectorRemoved(session_id=session_id, element_id=element_id))
        self._log.info("Seletor removido.", element_id=str(element_id), strategy=strategy)

    # ------------------------------------------------------------------
    # Além da superfície mínima do Port — necessário porque nenhum
    # método do Port recebe ``session_id``; ver ADR 0008.
    # ------------------------------------------------------------------

    def register_session_for_page(self, session_id: UUID, page_id: UUID) -> None:
        self._session_by_page[page_id] = session_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_element(self, element_id: UUID) -> Element:
        element = self._element_recorder.get_element(element_id)
        if element is None:
            raise ElementNotFoundError(f"Nenhum elemento capturado com o id {element_id}.")
        return element

    def _session_for_page(self, page_id: UUID) -> UUID:
        session_id = self._session_by_page.get(page_id)
        if session_id is None:
            raise PageSessionNotRegisteredError(
                f"Nenhuma sessão registrada para a página {page_id}; "
                "chame register_session_for_page() antes de analyze()."
            )
        return session_id

    @staticmethod
    def _build_css_selector(element: Element) -> str:
        if element.html_id:
            return f"#{element.html_id}"
        parts = [element.tag.lower()]
        parts.extend(f".{css_class}" for css_class in element.classes)
        return "".join(parts)

    @staticmethod
    def _build_relative_xpath(element: Element) -> str:
        tag = element.tag.lower()
        if element.html_id:
            return f"//{tag}[@id='{element.html_id}']"
        if element.name:
            return f"//{tag}[@name='{element.name}']"
        accessible = element.accessible_name or element.label
        if accessible:
            return f"//{tag}[@aria-label='{accessible}']"
        return f"//{tag}"

    def _build_absolute_xpath(self, element: Element) -> str:
        chain = [element.tag.lower()]
        current = element
        depth = 0
        while current.parent_element_id is not None and depth < _MAX_XPATH_DEPTH:
            parent = self._element_recorder.get_element(current.parent_element_id.value)
            if parent is None:
                break
            chain.append(parent.tag.lower())
            current = parent
            depth += 1
        chain.reverse()
        return "/" + "/".join(chain)

    def _publish(self, event: DomainEvent) -> None:
        self._event_publisher.publish(event)
