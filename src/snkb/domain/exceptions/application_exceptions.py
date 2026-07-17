"""Exceptions raised by the Application Controller (composition root;
Module Specifications 2.5, ARQ-002)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class CaptureAlreadyActiveError(KnowledgeBuilderError):
    """Raised when ``StartCapture`` is dispatched while another recording
    session is already active (RN-005: uma gravação por vez)."""
