"""Exceptions raised by the Session Manager (Module Specifications 4.15)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class SessionNotActiveError(KnowledgeBuilderError):
    """Raised when an operation requires an active session but none exists."""


class SessionAlreadyExistsError(KnowledgeBuilderError):
    """Raised when session creation collides with an existing session id."""


class InvalidSessionTransitionError(KnowledgeBuilderError):
    """Raised when a session status transition is not allowed (SRS 9.4)."""


class SessionExpiredError(KnowledgeBuilderError):
    """Raised when the ServiceNow authentication expired mid-recording."""


class DuplicatePageError(KnowledgeBuilderError):
    """Raised when a page identifier is already associated with another page."""


class InvalidMetadataError(KnowledgeBuilderError):
    """Raised when ``update_metadata`` receives a field the ``Session``
    entity does not expose for post-creation updates."""
