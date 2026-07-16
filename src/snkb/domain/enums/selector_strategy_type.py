"""Selector strategy types, ordered by priority (RN-010, RN-011, Module
Specifications Chapter 7, section 7.8)."""

from __future__ import annotations

from enum import StrEnum


class SelectorStrategyType(StrEnum):
    ID = "id"
    DATA_TESTID = "data_testid"
    NAME = "name"
    ARIA_LABEL = "aria_label"
    ROLE = "role"
    CSS = "css"
    XPATH_RELATIVE = "xpath_relative"
    XPATH_ABSOLUTE = "xpath_absolute"
