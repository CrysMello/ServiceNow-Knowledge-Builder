"""Session module.

Implementa ``SessionManagerPort`` (Module Specifications, Capítulo 4)
em ``session_manager.SessionManager`` — ver ADR 0005. Não depende de
Playwright, sistema de arquivos ou bibliotecas de log concretas; recebe
``EventPublisherPort`` e ``LogEnginePort`` por injeção de dependência,
como os demais módulos centrais.
"""
