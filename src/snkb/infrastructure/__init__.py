"""Infrastructure layer: concrete adapters for Playwright, the file
system and logging. Depends on ``application`` and ``domain`` contracts
only; never on ``presentation`` (ARQ, section 5).

No adapter classes are implemented yet — each subpackage is reserved for
the module that will be built in a later development step (see the
AI Development Guide, etapas 4-10).
"""
