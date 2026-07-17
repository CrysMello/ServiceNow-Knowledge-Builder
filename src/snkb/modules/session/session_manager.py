"""Implementação concreta de ``SessionManagerPort`` (Module
Specifications, Capítulo 4).

Único módulo autorizado a manter uma referência mutável à entidade
``Session`` (4.16). Não faz I/O, não importa Playwright nem sistema de
arquivos — é um registro em memória, válido pela duração do processo,
mutado apenas pelas transições de estado abaixo (ver ADR 0005 para a
tabela completa de transições e as decisões de design).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from snkb.domain.entities.session import Session
from snkb.domain.enums.session_status import SessionStatus
from snkb.domain.events.session_events import (
    SessionCreated,
    SessionExpired,
    SessionFailed,
    SessionFinished,
    SessionPaused,
    SessionResumed,
    SessionStarted,
    SessionTimeout,
)
from snkb.domain.exceptions.session_exceptions import (
    InvalidMetadataError,
    InvalidSessionTransitionError,
    SessionAlreadyExistsError,
    SessionNotActiveError,
)
from snkb.domain.value_objects.identifiers import SessionId

if TYPE_CHECKING:
    from snkb.application.ports.event_publisher_port import EventPublisherPort
    from snkb.application.ports.log_engine_port import LogEnginePort
    from snkb.domain.events.base import DomainEvent

_TERMINAL_STATUSES = frozenset(
    {
        SessionStatus.COMPLETED,
        SessionStatus.COMPLETED_WITH_WARNINGS,
        SessionStatus.INTERRUPTED,
        SessionStatus.FAILED,
    }
)

_ABORTABLE_STATUSES = frozenset(
    {
        SessionStatus.CREATED,
        SessionStatus.PREPARING,
        SessionStatus.WAITING_AUTHENTICATION,
        SessionStatus.READY,
        SessionStatus.RECORDING,
        SessionStatus.PAUSED,
        SessionStatus.FINALIZING,
    }
)

_MUTABLE_METADATA_FIELDS = frozenset(
    {
        "instance_name",
        "home_title",
        "service_now_version",
        "service_now_version_source",
        "language",
        "locale",
        "timezone",
        "browser",
        "browser_version",
        "operating_system",
        "screen_resolution",
        "viewport",
        "device_scale_factor",
        "zoom",
        "theme",
        "authenticated_user",
    }
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SessionManager:
    """Registro em memória e máquina de estados de sessões de gravação."""

    def __init__(
        self,
        event_publisher: EventPublisherPort,
        log_engine: LogEnginePort,
        now: Callable[[], datetime] = _utcnow,
        generate_session_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self._event_publisher = event_publisher
        self._log = log_engine
        self._now = now
        self._generate_session_id = generate_session_id
        self._sessions: dict[UUID, Session] = {}

    # ------------------------------------------------------------------
    # SessionManagerPort
    # ------------------------------------------------------------------

    def create_session(self, instance_url: str) -> Session:
        session_id = self._generate_session_id()
        if session_id in self._sessions:
            raise SessionAlreadyExistsError(
                f"Já existe uma sessão registrada com o id {session_id}."
            )

        session = Session(
            session_id=SessionId(value=session_id),
            instance_url=instance_url,
            created_at=self._now(),
            status=SessionStatus.CREATED,
        )
        self._sessions[session_id] = session
        self._publish(SessionCreated(session_id=session_id))
        self._log.info("Sessão criada.", session_id=str(session_id))
        return session

    def start_session(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(
            session,
            SessionStatus.RECORDING,
            frozenset({SessionStatus.READY, SessionStatus.RECOVERED}),
        )
        if session.recording_start is None:
            session.recording_start = self._now()
        self._publish(SessionStarted(session_id=session_id))
        self._log.info("Sessão iniciada.", session_id=str(session_id))

    def pause_session(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(session, SessionStatus.PAUSED, frozenset({SessionStatus.RECORDING}))
        self._publish(SessionPaused(session_id=session_id))
        self._log.info("Sessão pausada.", session_id=str(session_id))

    def resume_session(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(session, SessionStatus.RECORDING, frozenset({SessionStatus.PAUSED}))
        self._publish(SessionResumed(session_id=session_id))
        self._log.info("Sessão retomada.", session_id=str(session_id))

    def finish_session(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(
            session,
            SessionStatus.FINALIZING,
            frozenset({SessionStatus.RECORDING, SessionStatus.PAUSED}),
        )
        session.recording_end = self._now()
        # Microtransição interna: FINALIZING é sempre instantâneo e
        # sempre resolve para um dos dois estados terminais de sucesso,
        # dependendo de a sessão ter acumulado avisos (RF-0xx).
        session.status = (
            SessionStatus.COMPLETED_WITH_WARNINGS if session.warnings else SessionStatus.COMPLETED
        )
        self._publish(SessionFinished(session_id=session_id))
        self._log.info("Sessão finalizada.", session_id=str(session_id))

    def cancel_session(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(session, SessionStatus.INTERRUPTED, _ABORTABLE_STATUSES)
        self._publish(SessionFailed(session_id=session_id, reason="Sessão cancelada pelo usuário."))
        self._log.warning("Sessão cancelada.", session_id=str(session_id))

    def get_session(self, session_id: UUID) -> Session:
        return self._require_session(session_id)

    def get_statistics(self, session_id: UUID) -> dict[str, object]:
        """Estatísticas derivadas exclusivamente da entidade ``Session``.

        Contadores de páginas/elementos/screenshots pertencem aos
        módulos que ainda os produzem (Navigation Recorder, Element
        Recorder, Screenshot Engine) — nenhum deles existe ainda, então
        deliberadamente não são fabricados aqui como zeros enganosos
        (ver ADR 0005, "Consequências").
        """
        session = self._require_session(session_id)
        return {
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "recording_start": (
                session.recording_start.isoformat() if session.recording_start else None
            ),
            "recording_end": (session.recording_end.isoformat() if session.recording_end else None),
            "duration_seconds": session.duration_seconds,
            "warnings_count": len(session.warnings),
        }

    def update_metadata(self, session_id: UUID, metadata: dict[str, object]) -> None:
        session = self._require_session(session_id)
        unknown = set(metadata) - _MUTABLE_METADATA_FIELDS
        if unknown:
            raise InvalidMetadataError(f"Campos de metadados desconhecidos: {sorted(unknown)}")
        for key, value in metadata.items():
            setattr(session, key, value)

    def is_active(self, session_id: UUID) -> bool:
        session = self._require_session(session_id)
        return session.status not in _TERMINAL_STATUSES

    # ------------------------------------------------------------------
    # Transições adicionais (além da superfície mínima do Port) — o
    # Session Manager é o único dono da máquina de estados completa
    # (4.16), incluindo estados que nenhum método do Port aciona
    # diretamente. Ver ADR 0005.
    # ------------------------------------------------------------------

    def mark_preparing(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(session, SessionStatus.PREPARING, frozenset({SessionStatus.CREATED}))

    def mark_waiting_authentication(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(
            session,
            SessionStatus.WAITING_AUTHENTICATION,
            frozenset({SessionStatus.PREPARING}),
        )

    def mark_ready(self, session_id: UUID) -> None:
        session = self._require_session(session_id)
        self._transition(
            session, SessionStatus.READY, frozenset({SessionStatus.WAITING_AUTHENTICATION})
        )

    def expire_session(self, session_id: UUID) -> None:
        """Autenticação ServiceNow expirou no meio da gravação."""
        session = self._require_session(session_id)
        self._transition(session, SessionStatus.FAILED, _ABORTABLE_STATUSES)
        self._publish(SessionExpired(session_id=session_id))
        self._log.error("Sessão expirada.", session_id=str(session_id))

    def timeout_session(self, session_id: UUID) -> None:
        """A sessão ficou tempo demais sem progredir (ex.: login nunca
        concluído)."""
        session = self._require_session(session_id)
        self._transition(
            session,
            SessionStatus.FAILED,
            frozenset({SessionStatus.PREPARING, SessionStatus.WAITING_AUTHENTICATION}),
        )
        self._publish(SessionTimeout(session_id=session_id))
        self._log.error("Sessão expirou por tempo limite.", session_id=str(session_id))

    def recover_session(self, session_id: UUID) -> None:
        """Marca uma sessão ``interrupted`` como recuperada (RF-034,
        comando ``RecoverInterruptedSession``)."""
        session = self._require_session(session_id)
        self._transition(session, SessionStatus.RECOVERED, frozenset({SessionStatus.INTERRUPTED}))
        self._log.info("Sessão recuperada.", session_id=str(session_id))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_session(self, session_id: UUID) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotActiveError(f"Nenhuma sessão ativa com o id {session_id}.")
        return session

    @staticmethod
    def _transition(
        session: Session,
        new_status: SessionStatus,
        allowed_from: frozenset[SessionStatus],
    ) -> None:
        if session.status not in allowed_from:
            raise InvalidSessionTransitionError(
                f"Não é possível ir de {session.status.value!r} para {new_status.value!r}."
            )
        session.status = new_status

    def _publish(self, event: DomainEvent) -> None:
        self._event_publisher.publish(event)
