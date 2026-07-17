"""Port for the Application Controller (Module Specifications 2.5, ARQ-002).

The Presentation layer is only allowed to depend on this contract; it
must never call infrastructure managers (Browser Manager, Session
Manager, ...) directly.

``command``/``query`` are typed as ``object`` rather than a shared
``TypeVar`` because this Protocol is not itself generic: a single
controller instance dispatches many unrelated command and query types
(see ``application.commands.commands`` and
``application.queries.queries``), so no single type parameter could
correctly describe every call site.

``subscribe`` was intentionally left out of this Protocol until the
Application Controller itself was implemented (ADR 0003: "decisão
adiada"). Now that it exists (ADR 0012), the Presentation layer needs
it to receive domain events published in the background (RecordCommandHandler.
handle_domain_event) without depending on any concrete controller class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from snkb.domain.events.base import DomainEvent


class ApplicationControllerPort(Protocol):
    """Single entry point the CLI uses to dispatch commands, run queries,
    and subscribe to domain events published by the application layer."""

    def dispatch(self, command: object) -> None: ...
    def query(self, query: object) -> object: ...
    def subscribe(self, handler: Callable[[DomainEvent], None]) -> None: ...
