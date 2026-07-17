"""Exceptions raised by the Selector Analyzer (Module Specifications 7.18)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class SelectorGenerationError(KnowledgeBuilderError):
    """Raised when no selector strategy can be produced for an element."""


class NoViableSelectorError(KnowledgeBuilderError):
    """Raised when every candidate is invalid; the element is marked
    "Não Automatizável" instead of failing the whole session."""


class PageSessionNotRegisteredError(KnowledgeBuilderError):
    """Raised when ``analyze()``/``update_selector()`` need the session id
    of a page that was never registered via ``register_session_for_page()``."""
