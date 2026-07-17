"""Exceptions raised by the Element Recorder (Module Specifications 6.17)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class ElementCaptureError(KnowledgeBuilderError):
    """Raised when an element cannot be inspected (cross-origin, detached DOM)."""


class ShadowDomUnsupportedError(KnowledgeBuilderError):
    """Raised when a shadow root is closed or otherwise inaccessible (RF-049)."""


class NoPendingElementsError(KnowledgeBuilderError):
    """Raised when ``capture_elements()``/``update_element()`` are called
    without a prior ``observe_elements()``/``stage_element_update()``."""


class ElementNotFoundError(KnowledgeBuilderError):
    """Raised when ``update_element()``/``remove_element()`` reference an
    element id that was never captured."""
