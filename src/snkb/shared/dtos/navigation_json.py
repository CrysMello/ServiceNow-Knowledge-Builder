"""Schema for ``navigation.json`` (SRS section 10.3, RF-028)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NavigationNodeModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_id: UUID
    title: str
    url: str


class NavigationEdgeModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_page_id: UUID
    target_page_id: UUID
    event_id: UUID
    relation_type: str
    confidence: int
    timestamp: datetime
    evidence: str | None = None


class NavigationTimelineEntryModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    timestamp: datetime
    event_id: UUID
    page_id: UUID


class NavigationJsonModel(BaseModel):
    """Serializable representation of ``navigation.json``."""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    session_id: UUID
    nodes: list[NavigationNodeModel] = Field(default_factory=list)
    edges: list[NavigationEdgeModel] = Field(default_factory=list)
    timeline: list[NavigationTimelineEntryModel] = Field(default_factory=list)
