"""Schema for ``pages/<page_id>.json`` (SRS section 10.4, RF-029)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ElementModel(BaseModel):
    """Serializable element entry within a page file (SRS section 10.5)."""

    model_config = ConfigDict(frozen=True)

    element_id: UUID
    page_id: UUID
    frame_id: UUID
    semantic_type: str
    tag: str
    role: str | None = None
    accessible_name: str | None = None
    label: str | None = None
    placeholder: str | None = None
    html_id: str | None = None
    name: str | None = None
    classes: list[str] = Field(default_factory=list)
    required: bool = False
    readonly: bool = False
    disabled: bool = False
    visible: bool = True
    enabled: bool = True
    bounding_box: dict[str, object] | None = None
    fingerprint: str | None = None
    sensitivity_classification: str = "none"
    selectors: list[dict[str, object]] = Field(default_factory=list)


class FrameModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    frame_id: UUID
    origin: str
    selector: str | None = None
    parent_frame_id: UUID | None = None


class PageJsonModel(BaseModel):
    """Serializable representation of a single page artifact."""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    page_id: UUID
    revision_id: int = 1
    name_original: str
    name_reviewed: str | None = None
    title: str
    url_sanitized: str
    route: str | None = None
    frame_tree: list[FrameModel] = Field(default_factory=list)
    fingerprint: str
    first_seen: datetime
    last_seen: datetime | None = None
    parent_context: str | None = None
    elements: list[ElementModel] = Field(default_factory=list)
    screenshots: list[UUID] = Field(default_factory=list)
    messages: list[dict[str, object]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
