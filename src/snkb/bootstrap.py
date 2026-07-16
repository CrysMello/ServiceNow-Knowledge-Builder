"""Composition root: the only place authorized to choose concrete
implementations for the application's ports (AI Coding Standards,
section 10).

``create_application`` will eventually load configuration, construct the
Log Engine, Browser Manager, Session Manager, Navigation Recorder,
Element Recorder, Selector Analyzer, Screenshot Engine and Export
Engine adapters, wire them into an ``ApplicationControllerPort``
implementation, and hand that controller to the UI Manager.

None of those adapters exist yet, so this function intentionally raises
``NotImplementedError`` rather than returning a partially wired,
non-functional application.
"""

from __future__ import annotations

from snkb.presentation.contracts import UserInterfacePort


def create_application() -> UserInterfacePort:
    """Wire every adapter and return the ready-to-run UI entry point.

    Raises:
        NotImplementedError: always, until the modules listed in the
            AI Development Guide (etapas 4-11) are implemented.
    """
    raise NotImplementedError(
        "bootstrap.create_application: no module is implemented yet. "
        "This scaffolding step only prepares the architecture; wiring "
        "will be added once Browser Manager, Session Manager, "
        "Navigation Recorder, Element Recorder, Selector Analyzer, "
        "Screenshot Engine, Export Engine and Log Engine are built."
    )


def main() -> None:
    """Application entry point (invoked by ``python -m snkb``)."""
    application = create_application()
    application.run()


if __name__ == "__main__":
    main()
