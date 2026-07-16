"""Root of the application-specific exception hierarchy.

Every exception raised by ``snkb`` code (as opposed to third-party
libraries) must derive from ``KnowledgeBuilderError`` so that call sites can
distinguish expected domain failures from unexpected defects.
"""

from __future__ import annotations


class KnowledgeBuilderError(Exception):
    """Base error for the domain and application layers of the ServiceNow
    Knowledge Builder."""
