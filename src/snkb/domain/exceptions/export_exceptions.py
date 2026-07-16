"""Exceptions raised by the Export Engine (Module Specifications 9.17)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class ExportValidationError(KnowledgeBuilderError):
    """Raised when the produced Knowledge Base fails integrity validation."""


class ExportIntegrityError(KnowledgeBuilderError):
    """Raised when a checksum, reference or schema mismatch is detected."""


class SchemaIncompatibleError(KnowledgeBuilderError):
    """Raised when a reader encounters an unsupported ``schema_version``."""
