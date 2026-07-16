"""Screen and viewport geometry value objects (session.json fields)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Resolution:
    """Screen resolution in physical pixels."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Resolution dimensions must be positive.")


@dataclass(frozen=True, slots=True)
class Viewport:
    """Browser viewport size in CSS pixels."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Viewport dimensions must be positive.")
