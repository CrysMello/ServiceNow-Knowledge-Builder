"""Camada de apresentação: CLI (``snkb <comando>``).

Não contém regras de negócio. Depende apenas dos ports de
``application`` (``ApplicationControllerPort``), nunca diretamente de
``infrastructure`` (ARQ-002).

A implementação concreta fica inteiramente em
``snkb.presentation.cli``. Não existe mais um Protocol único
representando "a aplicação" (como havia em uma versão anterior deste
projeto baseada em GUI, ver ADR 0002): uma CLI de múltiplos comandos
independentes não tem um único ponto de entrada com ``run()``/
``mainloop()`` para abstrair — cada comando é sua própria invocação de
processo. Ver ADR 0003 para o histórico completo dessa decisão.
"""
