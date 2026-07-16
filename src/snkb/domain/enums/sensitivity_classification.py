"""Sensitivity classification applied to field values before persistence
(RS-002, RS-011, RF-011)."""

from __future__ import annotations

from enum import StrEnum


class SensitivityClassification(StrEnum):
    NONE = "none"
    MASKED = "masked"
    OMITTED = "omitted"
    SENSITIVE = "sensitive"
