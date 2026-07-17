"""Exceptions raised by the Screenshot Engine (Module Specifications 8.18)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class ScreenshotCaptureError(KnowledgeBuilderError):
    """Raised when a capture attempt fails or produces a corrupted file."""


class InsufficientDiskSpaceError(KnowledgeBuilderError):
    """Raised when there is not enough disk space to persist a screenshot."""


class NoPendingCaptureError(KnowledgeBuilderError):
    """Raised when ``capture()`` is called without a prior
    ``stage_capture()``, or when the capture policy disables screenshots
    entirely (``CapturePolicyModel.capture_screenshots``)."""


class ScreenshotNotFoundError(KnowledgeBuilderError):
    """Raised when ``delete()`` references a screenshot id that was never
    captured."""
