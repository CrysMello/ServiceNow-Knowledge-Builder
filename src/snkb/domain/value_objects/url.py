"""URL-related value objects.

Normalization and sanitization rules (RN-027, RS-005, RS-008) are the
responsibility of the module that produces a ``NormalizedUrl`` instance;
this value object only guarantees that a normalized URL is a non-empty
string once constructed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedUrl:
    """A URL with sensitive query parameters removed and casing normalized."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("NormalizedUrl cannot be empty.")

    def __str__(self) -> str:
        return self.value
