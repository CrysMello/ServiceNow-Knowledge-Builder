"""Generic command handler contract used by the Application Controller."""

from __future__ import annotations

from typing import Protocol, TypeVar

TCommand = TypeVar("TCommand", contravariant=True)
TResult = TypeVar("TResult", covariant=True)


class CommandHandlerPort(Protocol[TCommand, TResult]):
    """Executes a single command type and returns its result."""

    def handle(self, command: TCommand) -> TResult: ...
