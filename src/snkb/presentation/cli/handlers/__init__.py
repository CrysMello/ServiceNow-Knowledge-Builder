"""Orquestração de cada comando da CLI.

Depende apenas de ``ApplicationControllerPort``
(``snkb.application.services``) e dos auxiliares livres de
apresentação em ``snkb.presentation.cli`` (estado, contadores, fila de
eventos). Nunca importa Playwright, não interpreta seletores, não gera
JSON e não grava arquivos (Module Specifications 2.4,
"Responsabilidades Proibidas" — regra herdada do antigo UI Manager e
igualmente válida para a CLI).
"""
