"""Exceptions raised by the Navigation Recorder (Module Specifications 5.16)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class InvalidNavigationUrlError(KnowledgeBuilderError):
    """Raised when a navigated-to URL cannot be parsed or normalized."""


class RedirectLoopError(KnowledgeBuilderError):
    """Raised when a redirect chain does not converge (5.16, "Redirecionamento infinito")."""
