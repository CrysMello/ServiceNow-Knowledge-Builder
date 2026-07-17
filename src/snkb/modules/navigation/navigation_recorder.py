"""Implementação concreta de ``NavigationRecorderPort`` (Module
Specifications, Capítulo 5).

Assim como o Session Manager (ADR 0005), não faz I/O nem importa
Playwright: aprende sobre a navegação real exclusivamente através de
``observe_navigation()`` (chamado por quem já recebeu ``PageChanged``/
``UrlChanged`` do Browser Manager — hoje o futuro Application
Controller), nunca inspecionando o navegador diretamente. Ver ADR 0006
para as decisões de design desta camada de tradução "URL observada" →
"grafo de navegação".
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse
from uuid import UUID, uuid4

from snkb.domain.entities.navigation_edge import NavigationEdge
from snkb.domain.entities.page import Page
from snkb.domain.enums.navigation_type import NavigationType
from snkb.domain.enums.relation_type import RelationType
from snkb.domain.events.navigation_events import (
    NavigationFinished,
    NavigationStarted,
    NavigationUrlChanged,
    PageCaptured,
    PageClosed,
    PageOpened,
    PageUpdated,
    RedirectDetected,
)
from snkb.domain.exceptions.navigation_exceptions import (
    InvalidNavigationUrlError,
    NavigationAlreadyActiveError,
    NavigationNotActiveError,
    NoPendingNavigationError,
    PageNotFoundError,
    RedirectLoopError,
)
from snkb.domain.value_objects.identifiers import EventId, PageId, SessionId
from snkb.domain.value_objects.url import NormalizedUrl

if TYPE_CHECKING:
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.domain.events.base import DomainEvent

_SCHEMA_VERSION = "1.0"
_DEFAULT_MAX_REDIRECT_CHAIN = 10


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class _PendingObservation:
    """URL observada para uma aba, ainda não convertida em ``Page``."""

    url: str
    title: str | None


class NavigationRecorder:
    """Constrói o grafo e o histórico de navegação de uma sessão a partir
    de observações de URL já normalizadas (sem I/O próprio)."""

    def __init__(
        self,
        event_publisher: EventPublisherPort,
        log_engine: LogEnginePort,
        now: Callable[[], datetime] = _utcnow,
        generate_id: Callable[[], UUID] = uuid4,
        max_redirect_chain: int = _DEFAULT_MAX_REDIRECT_CHAIN,
    ) -> None:
        self._event_publisher = event_publisher
        self._log = log_engine
        self._now = now
        self._generate_id = generate_id
        self._max_redirect_chain = max_redirect_chain

        self._session_id: UUID | None = None
        self._running = False

        self._pending_by_tab: dict[str, _PendingObservation] = {}
        self._redirect_chain_length: dict[str, int] = {}
        self._last_observed_tab_id: str | None = None
        self._pages_by_fingerprint: dict[str, Page] = {}
        self._history: list[Page] = []
        self._open_page_ids: set[UUID] = set()
        self._tab_id_by_page: dict[UUID, str] = {}
        self._current_page: Page | None = None
        self._edges: list[NavigationEdge] = []
        self._timeline: list[tuple[int, UUID, datetime, UUID]] = []

    # ------------------------------------------------------------------
    # NavigationRecorderPort
    # ------------------------------------------------------------------

    def start(self, session_id: UUID) -> None:
        if self._running:
            raise NavigationAlreadyActiveError(
                "Já existe uma gravação de navegação em andamento; chame stop() antes."
            )
        self._session_id = session_id
        self._running = True
        self._publish(NavigationStarted(session_id=session_id))
        self._log.info("Gravação de navegação iniciada.", session_id=str(session_id))

    def stop(self) -> None:
        session_id = self._require_running()
        self._running = False
        self._publish(NavigationFinished(session_id=session_id))
        self._log.info("Gravação de navegação finalizada.", session_id=str(session_id))

    def capture_page(self) -> Page:
        session_id = self._require_running()
        if self._last_observed_tab_id is None:
            raise NoPendingNavigationError(
                "Nenhuma navegação observada ainda; "
                "chame observe_navigation() antes de capture_page()."
            )
        tab_id = self._last_observed_tab_id
        observation = self._pending_by_tab.pop(tab_id, None)
        if observation is None:
            raise NoPendingNavigationError(
                f"A aba {tab_id!r} não tem nenhuma navegação pendente de captura."
            )
        self._redirect_chain_length.pop(tab_id, None)

        normalized_url = self._normalize_url(observation.url)
        fingerprint = self._compute_fingerprint(normalized_url)
        now = self._now()

        existing = self._pages_by_fingerprint.get(fingerprint)
        if existing is not None:
            existing.last_seen = now
            if observation.title and observation.title != existing.title:
                existing.title = observation.title
            page = existing
            is_new = False
        else:
            page = Page(
                page_id=PageId(value=self._generate_id()),
                session_id=SessionId(value=session_id),
                name_original=self._derive_name(normalized_url),
                title=observation.title or normalized_url.value,
                url=normalized_url,
                fingerprint=fingerprint,
                first_seen=now,
            )
            self._pages_by_fingerprint[fingerprint] = page
            self._history.append(page)
            self._open_page_ids.add(page.page_id.value)
            is_new = True

        self._tab_id_by_page[page.page_id.value] = tab_id
        self._link_from_current_page(page, now)
        self._current_page = page

        captured = PageCaptured(
            session_id=session_id,
            page_id=page.page_id.value,
            normalized_url=normalized_url.value,
        )
        self._publish(captured)
        self._append_timeline(captured, page.page_id.value)
        if is_new:
            self._publish(PageOpened(session_id=session_id, page_id=page.page_id.value))
        self._log.info(
            "Página capturada.", session_id=str(session_id), page_id=str(page.page_id.value)
        )
        return page

    def update_page(self, page_id: UUID) -> Page:
        session_id = self._require_running()
        page = self._find_page(page_id)
        tab_id = self._tab_id_by_page.get(page_id)
        observation = self._pending_by_tab.pop(tab_id, None) if tab_id is not None else None
        if observation is not None:
            if observation.title and observation.title != page.title:
                page.title = observation.title
                page.revision_id += 1
            page.last_seen = self._now()
        self._publish(PageUpdated(session_id=session_id, page_id=page_id))
        self._log.info("Página atualizada.", session_id=str(session_id), page_id=str(page_id))
        return page

    def close_page(self, page_id: UUID) -> None:
        session_id = self._require_running()
        self._find_page(page_id)
        self._open_page_ids.discard(page_id)
        if self._current_page is not None and self._current_page.page_id.value == page_id:
            self._current_page = None
        self._publish(PageClosed(session_id=session_id, page_id=page_id))
        self._log.info("Página fechada.", session_id=str(session_id), page_id=str(page_id))

    def get_current_page(self) -> Page | None:
        return self._current_page

    def get_navigation_graph(self) -> list[NavigationEdge]:
        return list(self._edges)

    def get_page_history(self) -> list[Page]:
        return list(self._history)

    def export_navigation(self) -> dict[str, object]:
        if self._session_id is None:
            raise NavigationNotActiveError(
                "Nenhuma sessão associada; chame start() antes de exportar."
            )
        return {
            "schema_version": _SCHEMA_VERSION,
            "session_id": str(self._session_id),
            "nodes": [
                {"page_id": str(page.page_id.value), "title": page.title, "url": page.url.value}
                for page in self._history
            ],
            "edges": [
                {
                    "source_page_id": str(edge.source_page_id.value),
                    "target_page_id": str(edge.target_page_id.value),
                    "event_id": str(edge.event_id.value),
                    "relation_type": edge.relation_type.value,
                    "confidence": edge.confidence,
                    "timestamp": edge.timestamp.isoformat(),
                    "evidence": edge.evidence,
                }
                for edge in self._edges
            ],
            "timeline": [
                {
                    "sequence": sequence,
                    "timestamp": timestamp.isoformat(),
                    "event_id": str(event_id),
                    "page_id": str(page_id),
                }
                for sequence, event_id, timestamp, page_id in self._timeline
            ],
        }

    def clear_navigation(self) -> None:
        self._session_id = None
        self._running = False
        self._reset_state()

    # ------------------------------------------------------------------
    # Além da superfície mínima do Port — recebe as observações de
    # navegação que o Browser Manager publica como eventos de domínio
    # (``PageChanged``/``UrlChanged``); ver ADR 0006.
    # ------------------------------------------------------------------

    def observe_navigation(self, tab_id: str, url: str, title: str | None = None) -> None:
        session_id = self._require_running()
        pending = self._pending_by_tab.get(tab_id)
        if pending is not None:
            chain = self._redirect_chain_length.get(tab_id, 1) + 1
            if chain > self._max_redirect_chain:
                raise RedirectLoopError(
                    f"Mais de {self._max_redirect_chain} redirecionamentos consecutivos "
                    f"na aba {tab_id!r} sem uma captura confirmada."
                )
            self._redirect_chain_length[tab_id] = chain
            self._publish(RedirectDetected(session_id=session_id, from_url=pending.url, to_url=url))
        self._pending_by_tab[tab_id] = _PendingObservation(url=url, title=title)
        self._last_observed_tab_id = tab_id
        self._publish(NavigationUrlChanged(session_id=session_id, url=url))

    def get_tab_id_for_page(self, page_id: UUID) -> str | None:
        """Além da superfície mínima do Port — usado pelo Browser Data
        Collector (ADR 0013) para reenviar um título obtido depois da
        captura inicial via ``observe_navigation()`` + ``update_page()``,
        fechando a lacuna já documentada na ADR 0006."""
        return self._tab_id_by_page.get(page_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _reset_state(self) -> None:
        self._pending_by_tab = {}
        self._redirect_chain_length = {}
        self._last_observed_tab_id = None
        self._pages_by_fingerprint = {}
        self._history = []
        self._open_page_ids = set()
        self._tab_id_by_page = {}
        self._current_page = None
        self._edges = []
        self._timeline = []

    def _require_running(self) -> UUID:
        if not self._running or self._session_id is None:
            raise NavigationNotActiveError(
                "A gravação de navegação não está ativa; chame start() antes."
            )
        return self._session_id

    def _find_page(self, page_id: UUID) -> Page:
        for page in self._history:
            if page.page_id.value == page_id:
                return page
        raise PageNotFoundError(f"Nenhuma página capturada com o id {page_id}.")

    def _link_from_current_page(self, page: Page, timestamp: datetime) -> None:
        previous = self._current_page
        if previous is None or previous.page_id == page.page_id:
            return
        edge = NavigationEdge(
            source_page_id=previous.page_id,
            target_page_id=page.page_id,
            event_id=EventId(value=self._generate_id()),
            navigation_type=NavigationType.MANUAL,
            relation_type=RelationType.OBSERVED,
            confidence=100,
            timestamp=timestamp,
        )
        self._edges.append(edge)

    def _append_timeline(self, event: DomainEvent, page_id: UUID) -> None:
        sequence = len(self._timeline)
        self._timeline.append((sequence, event.event_id, event.occurred_at, page_id))

    @staticmethod
    def _normalize_url(raw: str) -> NormalizedUrl:
        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            raise InvalidNavigationUrlError(f"URL de navegação inválida: {raw!r}")
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), fragment=""
        )
        return NormalizedUrl(value=urlunparse(normalized))

    @staticmethod
    def _compute_fingerprint(url: NormalizedUrl) -> str:
        return hashlib.sha256(url.value.encode("utf-8")).hexdigest()

    @staticmethod
    def _derive_name(url: NormalizedUrl) -> str:
        path = urlparse(url.value).path.strip("/")
        if not path:
            return "home"
        return path.rsplit("/", maxsplit=1)[-1]

    def _publish(self, event: DomainEvent) -> None:
        self._event_publisher.publish(event)
