"""Semantic classification of interface components (RN-043).

Enumerated from Business Rules ("Classificação de Componentes") and Module
Specifications Chapter 6, section 6.8.
"""

from __future__ import annotations

from enum import StrEnum


class ElementSemanticType(StrEnum):
    # Fields
    TEXTBOX = "textbox"
    TEXTAREA = "textarea"
    PASSWORD = "password"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    LOOKUP = "lookup"
    REFERENCE = "reference"

    # Selection
    COMBOBOX = "combobox"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO_BUTTON = "radio_button"
    TOGGLE = "toggle"
    SWITCH = "switch"

    # Navigation
    MENU = "menu"
    SUBMENU = "submenu"
    LINK = "link"
    BREADCRUMB = "breadcrumb"
    TAB = "tab"
    ACCORDION = "accordion"
    SIDEBAR = "sidebar"

    # Buttons
    BUTTON = "button"
    ICON_BUTTON = "icon_button"
    FLOATING_BUTTON = "floating_button"
    ACTION_BUTTON = "action_button"
    CONTEXT_MENU = "context_menu"

    # Structures
    TABLE = "table"
    GRID = "grid"
    CARD = "card"
    PANEL = "panel"
    CONTAINER = "container"
    SECTION = "section"
    FORM = "form"
    FIELDSET = "fieldset"
    RELATED_LIST = "related_list"

    # Windows
    POPUP = "popup"
    MODAL = "modal"
    DIALOG = "dialog"
    TOAST = "toast"
    NOTIFICATION = "notification"

    # ServiceNow-specific
    FORM_LAYOUT = "form_layout"
    WORKSPACE_COMPONENT = "workspace_component"
    UI_BUILDER_COMPONENT = "ui_builder_component"
    SERVICE_PORTAL_WIDGET = "service_portal_widget"
    NOW_EXPERIENCE_COMPONENT = "now_experience_component"

    UNKNOWN = "unknown"
