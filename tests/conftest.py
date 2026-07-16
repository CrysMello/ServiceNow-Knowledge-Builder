"""Shared, deterministic fixtures for the test suite (AI Coding
Standards, section 19: "Fixtures serão determinísticas e reutilizáveis")."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest


@pytest.fixture
def fixed_session_uuid() -> UUID:
    """A stable UUID so assertions never depend on random generation."""
    return UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0")


@pytest.fixture
def fixed_page_uuid() -> UUID:
    return UUID("1c2d3e4f-5a6b-47c8-89d0-1234567890ab")


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 7, 16, 9, 0, 0, tzinfo=UTC)
