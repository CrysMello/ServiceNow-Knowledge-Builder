"""Exceptions raised by the Browser Data Collector (infrastructure
adapter that bridges Playwright to Element Recorder, Selector Analyzer
and Screenshot Engine — ver ADR 0013)."""

from __future__ import annotations

from snkb.domain.exceptions.base import KnowledgeBuilderError


class CollectorNotActiveError(KnowledgeBuilderError):
    """Raised when ``capture_current_page()``/``stop()`` are called
    without a prior ``start()``."""
