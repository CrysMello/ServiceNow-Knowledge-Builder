"""Port for opening a directory in the OS file explorer (``snkb open``,
Module Specifications, Chapter 2, section 2.12: ``OPEN_EXPORT_FOLDER``).

A dedicated Port rather than a direct OS call from the application layer
because ``application/`` may never know infrastructure concrete types
(ARQ-001) — only ``infrastructure/`` may call ``os.startfile``/
``subprocess``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FolderOpenerPort(Protocol):
    """Opens a directory in the operating system's file explorer."""

    def open(self, path: Path) -> None: ...
