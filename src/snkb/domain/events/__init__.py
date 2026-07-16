"""Domain events: immutable facts published through the Event Publisher.

Events never carry infrastructure references (Playwright ``Page``, UI
widgets, file handles) — only plain data (PW-006).
"""
