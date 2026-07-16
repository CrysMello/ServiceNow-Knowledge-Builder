"""Camada de apresentação: UI Manager em CustomTkinter.

Não contém regras de negócio (Module Specifications, Capítulo 2, seção
2.1). Depende apenas dos ports de ``application``, nunca diretamente de
``infrastructure`` (ARQ-002).

A classe concreta ``CustomTkinterUserInterface`` fica em
``snkb.presentation.main_window`` e não é reexportada aqui de propósito:
isso evita que qualquer import deste pacote (por exemplo, apenas para
usar ``contracts.UserInterfacePort`` como tipo) exija o CustomTkinter
instalado. Importe-a explicitamente quando precisar da implementação
concreta.
"""
