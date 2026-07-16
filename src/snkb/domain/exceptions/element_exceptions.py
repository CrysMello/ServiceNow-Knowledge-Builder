"""Exceptions raised by the Element Recorder (Module Specifications 6.17)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class ElementCaptureError(KnowledgeBuilderError):
    """Raised when an element cannot be inspected (cross-origin, detached DOM)."""


class ShadowDomUnsupportedError(KnowledgeBuilderError):
    """Raised when a shadow root is closed or otherwise inaccessible (RF-049)."""
