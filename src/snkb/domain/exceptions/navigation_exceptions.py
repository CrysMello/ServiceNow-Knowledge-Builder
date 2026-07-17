"""Exceptions raised by the Navigation Recorder (Module Specifications 5.16)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class InvalidNavigationUrlError(KnowledgeBuilderError):
    """Raised when a navigated-to URL cannot be parsed or normalized."""


class RedirectLoopError(KnowledgeBuilderError):
    """Raised when a redirect chain does not converge (5.16, "Redirecionamento infinito")."""


class NavigationNotActiveError(KnowledgeBuilderError):
    """Raised when an operation requires ``start()`` to have been called
    for the current session, but it has not."""


class NavigationAlreadyActiveError(KnowledgeBuilderError):
    """Raised when ``start()`` is called while a session is already being
    recorded (``stop()``/``clear_navigation()`` must run first)."""


class NoPendingNavigationError(KnowledgeBuilderError):
    """Raised when ``capture_page()`` is called before any navigation has
    been observed via ``observe_navigation()``."""


class PageNotFoundError(KnowledgeBuilderError):
    """Raised when ``update_page()``/``close_page()`` reference a page id
    that was never captured in the current session."""
