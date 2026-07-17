"""Screenshots module.

Implementa ``ScreenshotEnginePort`` (Module Specifications, Capítulo
8) em ``screenshot_engine.ScreenshotEngine`` — ver ADR 0009. Sem I/O,
sem Playwright: cataloga metadados de capturas já realizadas via
``stage_capture()``; o conteúdo binário é gravado em disco
exclusivamente pelo Export Engine (ver docstring de
``domain.entities.screenshot.Screenshot``).
"""
