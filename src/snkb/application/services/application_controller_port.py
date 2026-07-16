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
"""

from __future__ import annotations

from typing import Protocol


class ApplicationControllerPort(Protocol):
    """Single entry point the UI Manager uses to dispatch commands and
    queries into the application layer."""

    def dispatch(self, command: object) -> None: ...
    def query(self, query: object) -> object: ...
