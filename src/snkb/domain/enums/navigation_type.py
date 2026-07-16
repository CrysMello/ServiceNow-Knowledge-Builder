"""Classification of how a navigation transition was triggered.

See Module Specifications, Chapter 5, section 5.9.
"""

from __future__ import annotations

from enum import StrEnum


class NavigationType(StrEnum):
    MANUAL = "manual"
    REDIRECT = "redirect"
    REFRESH = "refresh"
    BACK = "back"
    FORWARD = "forward"
    POPUP = "popup"
    MODAL = "modal"
    RELATED_LIST = "related_list"
    NEW_TAB = "new_tab"
