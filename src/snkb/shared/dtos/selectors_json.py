"""Schema for ``selectors.json`` (SRS section 10.5, RF-030)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SelectorCandidateModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: str
    value: str
    uniqueness_count: int | None = None
    confidence_score: int = Field(ge=0, le=100)
    stability_score: int = Field(ge=0, le=100)
    validated_at: datetime | None = None
    notes: str | None = None


class ElementSelectorsModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_id: UUID
    element_id: UUID
    best_strategy: SelectorCandidateModel | None = None
    fallback_strategies: list[SelectorCandidateModel] = Field(default_factory=list)


class SelectorsJsonModel(BaseModel):
    """Serializable representation of ``selectors.json``."""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    session_id: UUID
    elements: list[ElementSelectorsModel] = Field(default_factory=list)
