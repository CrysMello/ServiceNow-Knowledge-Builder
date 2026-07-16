"""Schema for ``statistics.json`` (Export Engine 9.11)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StatisticsJsonModel(BaseModel):
    """Aggregated counters computed once a session finishes."""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    session_id: UUID
    total_pages: int = 0
    total_elements: int = 0
    total_selectors: int = 0
    total_screenshots: int = 0
    total_events: int = 0
    total_logs: int = 0
    capture_duration_seconds: float | None = None
    export_duration_seconds: float | None = None
    error_count: int = 0
    warning_count: int = 0
