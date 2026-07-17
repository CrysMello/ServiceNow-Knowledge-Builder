"""Elements module.

Implementa ``ElementRecorderPort`` (Module Specifications, Capítulo 6)
em ``element_recorder.ElementRecorder`` — ver ADR 0007. Não depende de
Playwright nem de nenhum outro módulo central: identifica e classifica
elementos via ``observe_elements()``, alimentado por quem já tem acesso
ao DOM real (hoje o futuro Application Controller). Nunca lê nem
armazena o valor de um campo.
"""
