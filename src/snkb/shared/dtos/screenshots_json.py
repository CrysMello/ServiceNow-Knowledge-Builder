"""Schema for screenshot metadata entries (Module Specifications 8.22)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScreenshotMetadataModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    file: str
    type: str
    timestamp: datetime
    width: int
    height: int


class ScreenshotsJsonModel(BaseModel):
    """Serializable representation of the per-page screenshot manifest."""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    session_id: UUID
    page_id: UUID
    screenshots: list[ScreenshotMetadataModel] = Field(default_factory=list)
