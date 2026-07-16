"""Schema for ``manifest.json`` (SRS section 10.6, Export Engine 9.10)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ManifestFileEntryModel(BaseModel):
    """One inventoried file within the exported Knowledge Base."""

    model_config = ConfigDict(frozen=True)

    path: str
    size_bytes: int
    sha256: str
    content_type: str


class ManifestJsonModel(BaseModel):
    """Serializable representation of ``manifest.json``.

    The validator described in SRS 10.6 (missing file, mismatched
    checksum, broken reference) is implemented by the Export Engine, not
    by this schema.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str
    session_id: UUID
    generator: str
    created_at: datetime
    files: list[ManifestFileEntryModel] = Field(default_factory=list)
