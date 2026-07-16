"""Exceptions raised by the Browser Manager (Module Specifications 3.13)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class BrowserInitializationError(KnowledgeBuilderError):
    """Raised when Playwright or the browser process fail to start."""


class BrowserTimeoutError(KnowledgeBuilderError):
    """Raised when a browser operation exceeds its configured timeout."""


class BrowserClosedUnexpectedlyError(KnowledgeBuilderError):
    """Raised when the monitored browser closes outside of normal shutdown."""


class PageUnavailableError(KnowledgeBuilderError):
    """Raised when the active page cannot be reached or has been discarded."""


class InvalidUrlError(KnowledgeBuilderError):
    """Raised when a configured or navigated-to URL fails validation."""
