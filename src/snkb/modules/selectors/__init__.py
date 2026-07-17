"""Selectors module.

Implementa ``SelectorAnalyzerPort`` (Module Specifications, Capítulo
7) em ``selector_analyzer.SelectorAnalyzer`` — ver ADR 0008. Única
dependência de outro módulo central: ``ElementRecorderPort`` (7.5),
já que todos os atributos necessários para gerar seletores já foram
capturados e classificados pelo Element Recorder. Sem I/O, sem
Playwright.
"""
