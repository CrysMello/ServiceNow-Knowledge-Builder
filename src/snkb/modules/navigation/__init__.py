"""Navigation module.

Implementa ``NavigationRecorderPort`` (Module Specifications, Capítulo
5) em ``navigation_recorder.NavigationRecorder`` — ver ADR 0006. Não
depende de Playwright nem de nenhum outro módulo central: aprende
sobre a navegação real via ``observe_navigation()``, alimentado por
quem já recebeu ``PageChanged``/``UrlChanged`` do Browser Manager.
"""
