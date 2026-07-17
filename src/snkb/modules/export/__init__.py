"""Export module.

Implementa ``ExportEnginePort`` (Module Specifications, Capítulo 9) em
``export_engine.ExportEngine`` — ver ADR 0010. Único módulo central que
grava arquivos em disco (JSON via Pydantic, HTML do relatório), usando
apenas a biblioteca padrão — nunca captura nada sozinho, apenas
consolida o que Session Manager, Navigation Recorder, Element
Recorder, Selector Analyzer e Screenshot Engine já produziram (9.5).
"""
