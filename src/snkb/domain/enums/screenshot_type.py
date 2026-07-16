"""Screenshot capture types (Module Specifications Chapter 8, section 8.8)."""

from __future__ import annotations

from enum import StrEnum


class ScreenshotType(StrEnum):
    FULL_PAGE = "full_page"
    VIEWPORT = "viewport"
    MODAL = "modal"
    POPUP = "popup"
    ELEMENT = "element"
    REGION = "region"
