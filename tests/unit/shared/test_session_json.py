"""Validates the ``session.json`` schema against the SRS 10.2 example."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from snkb.shared.dtos.session_json import (
    ScreenResolutionModel,
    SessionJsonModel,
    ViewportModel,
)


def test_session_json_model_accepts_the_srs_example() -> None:
    model = SessionJsonModel(
        schema_version="1.0",
        recording_id=UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0"),
        instance_url="https://empresa.service-now.com",
        recording_start=datetime(2026, 7, 16, 9, 0, 0, tzinfo=UTC),
        recording_end=datetime(2026, 7, 16, 9, 25, 13, tzinfo=UTC),
        status="completed",
        browser="Microsoft Edge",
        browser_version="150.x",
        operating_system="Windows 11",
        screen_resolution=ScreenResolutionModel(width=1920, height=1080),
        viewport=ViewportModel(width=1920, height=1000),
        authenticated_user=None,
    )

    assert model.status == "completed"
    assert model.warnings == []


def test_session_json_model_serializes_null_for_optional_fields() -> None:
    model = SessionJsonModel(
        schema_version="1.0",
        recording_id=UUID("7d6c6f24-6c89-4b58-a9cd-bc88a84f15f0"),
        instance_url="https://empresa.service-now.com",
        recording_start=datetime(2026, 7, 16, 9, 0, 0, tzinfo=UTC),
        status="recording",
        browser="Microsoft Edge",
        browser_version="150.x",
        operating_system="Windows 11",
        screen_resolution=ScreenResolutionModel(width=1920, height=1080),
        viewport=ViewportModel(width=1920, height=1000),
    )

    dumped = model.model_dump(mode="json")

    assert dumped["authenticated_user"] is None
    assert dumped["recording_end"] is None
