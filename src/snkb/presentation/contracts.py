"""Public contract of the UI Manager (Module Specifications, Chapter 2).

The concrete CustomTkinter implementation is a future module and is not
part of this scaffold.
"""

from __future__ import annotations

from typing import Protocol


class UserInterfacePort(Protocol):
    """Entry point for the desktop UI. Receives a single
    ``ApplicationControllerPort`` instance at construction time
    (ARQ-002) and never touches infrastructure managers directly."""

    def run(self) -> None: ...
    def shutdown(self) -> None: ...
