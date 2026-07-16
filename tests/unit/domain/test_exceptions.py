"""Unit tests for the domain exception hierarchy."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError
from snkb.domain.exceptions.browser_exceptions import BrowserInitializationError
from snkb.domain.exceptions.export_exceptions import ExportValidationError
from snkb.domain.exceptions.session_exceptions import SessionNotActiveError


def test_all_domain_exceptions_derive_from_knowledge_builder_error() -> None:
    assert issubclass(SessionNotActiveError, KnowledgeBuilderError)
    assert issubclass(BrowserInitializationError, KnowledgeBuilderError)
    assert issubclass(ExportValidationError, KnowledgeBuilderError)


def test_domain_exceptions_carry_their_message() -> None:
    error = SessionNotActiveError("No active session for this operation.")

    assert str(error) == "No active session for this operation."
