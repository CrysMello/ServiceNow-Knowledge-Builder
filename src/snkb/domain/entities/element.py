"""Element entity: an interactive or structural interface component
(SRS section 10.5, Module Specifications Chapter 6)."""

from __future__ import annotations

from dataclasses import dataclass, field

from snkb.domain.enums.element_semantic_type import ElementSemanticType
from snkb.domain.enums.sensitivity_classification import SensitivityClassification
from snkb.domain.value_objects.identifiers import ElementId, FrameId, PageId


@dataclass(slots=True)
class Element:
    """A single component identified on a page by the Element Recorder."""

    element_id: ElementId
    page_id: PageId
    frame_id: FrameId
    semantic_type: ElementSemanticType
    tag: str

    role: str | None = None
    accessible_name: str | None = None
    label: str | None = None
    placeholder: str | None = None
    html_id: str | None = None
    name: str | None = None
    classes: tuple[str, ...] = field(default_factory=tuple)

    required: bool = False
    readonly: bool = False
    disabled: bool = False
    visible: bool = True
    enabled: bool = True

    fingerprint: str | None = None
    sensitivity_classification: SensitivityClassification = SensitivityClassification.NONE

    parent_element_id: ElementId | None = None
