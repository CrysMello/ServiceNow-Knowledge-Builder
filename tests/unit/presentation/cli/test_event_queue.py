"""Testes da fila thread-safe de eventos de domínio."""

from __future__ import annotations

import threading
from uuid import UUID

from snkb.domain.events.session_events import SessionStarted
from snkb.presentation.cli.event_queue import DomainEventQueue


def test_drain_returns_events_in_arrival_order(fixed_session_uuid: UUID) -> None:
    queue_ = DomainEventQueue()
    first = SessionStarted(session_id=fixed_session_uuid)
    second = SessionStarted(session_id=fixed_session_uuid)

    queue_.submit(first)
    queue_.submit(second)

    assert queue_.drain() == [first, second]


def test_drain_is_empty_when_nothing_was_submitted() -> None:
    queue_ = DomainEventQueue()

    assert queue_.drain() == []


def test_submit_from_another_thread_is_visible_to_drain(fixed_session_uuid: UUID) -> None:
    queue_ = DomainEventQueue()
    event = SessionStarted(session_id=fixed_session_uuid)

    thread = threading.Thread(target=queue_.submit, args=(event,))
    thread.start()
    thread.join()

    assert queue_.drain() == [event]
