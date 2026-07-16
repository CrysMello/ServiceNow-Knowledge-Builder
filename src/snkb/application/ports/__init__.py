"""Ports: abstractions that infrastructure adapters must fulfill (PR-002,
PR-003). Defined as ``typing.Protocol`` classes so infrastructure classes
do not need to inherit from them explicitly (structural typing).

None of these protocols contain behaviour; they exist to let the
Application layer depend on an abstraction instead of a concrete
Playwright/CustomTkinter/filesystem implementation.
"""
