# ADR 0003 — Adequação da camada de apresentação para CLI

## Status

Aceito — 2026-07-16.

## Contexto

O produto passou a ser definido como uma aplicação de linha de comando
(`snkb record`, `snkb status`, `snkb validate`, `snkb open`, `snkb
logs`, `snkb config`, `snkb version`), substituindo a definição
anterior orientada a desktop GUI (CustomTkinter, ADR 0002 — Module
Specifications Capítulo 2). Conforme instrução explícita do produto,
esta definição de CLI prevalece sobre a documentação antiga de GUI
para a camada de apresentação.

Ao revisar o código existente antes de qualquer alteração, confirmou-se
por leitura direta (não por suposição) que a lógica de estado,
contadores e fila de eventos do UI Manager já havia sido separada dos
widgets do CustomTkinter (nenhum dos cinco módulos correspondentes
importava `customtkinter`). Isso permitiu que a adequação para CLI
fosse uma substituição localizada da "casca" de apresentação, e não uma
reescrita da lógica.

## Decisão

### O que foi preservado sem alteração de comportamento

- `domain/`, `application/` (ports, commands, queries,
  `ApplicationControllerPort`), `shared/dtos/*`, `infrastructure/*`,
  `modules/*`, `schemas/*`, `config/*` — nenhum arquivo tocado.
- A lógica de: transição de estados a partir de eventos de domínio
  consumidos, agregação de contadores, e a fila thread-safe de
  bridging entre threads produtoras de eventos e a thread que os
  processa. Só foram movidas para `presentation/cli/` e renomeadas
  (ver abaixo); nenhuma transição de estado ou regra de contagem mudou.
- As mensagens obrigatórias da interface (SRS 11.1), incluindo "Nenhuma
  credencial foi armazenada.", agora exibidas no rodapé de toda
  execução de `snkb record`.
- A regra de segurança de que eventos de domínio nunca têm seus campos
  impressos — só o nome da classe (Module Specifications 2.16).

### O que foi renomeado (removendo conotação de GUI)

| Antes | Depois |
| --- | --- |
| `UiState` | `RecordingState` |
| `UiStateMachine` | `RecordingStateMachine` |
| `UiEventQueue` | `DomainEventQueue` |
| `StatusAggregator` | `RecordingCounterAggregator` |
| `SessionPanelViewModel` | `SessionInfo` |
| `StatusPanelViewModel` | `RecordingCounters` |
| `LogEntryViewModel` | `LogEntry` |

### O que foi removido

- `presentation/main_window.py` (implementação concreta CustomTkinter)
  e seu teste de fumaça (`tests/integration/test_main_window_smoke.py`).
- `presentation/contracts.py` (`UserInterfacePort`): modelava "um único
  app com `run()`/`mainloop()`". Uma CLI de 7 subcomandos independentes
  não tem esse único ponto de entrada — cada comando é sua própria
  invocação de processo. O método `handle_domain_event` (que a
  interface antiga expunha) passou a ser um método concreto de
  `RecordCommandHandler`, o único comando que de fato recebe eventos de
  domínio durante a execução.
- Dependência `customtkinter` (de `pyproject.toml` e
  `requirements.txt`) e o override de mypy correspondente.

### O que foi criado

Estrutura `presentation/cli/` (ver `docs/architecture/README.md` para
o mapa completo):

- `main.py`: app Typer, registra os 7 comandos.
- `commands/*.py`: uma função fina por subcomando — só parsing de
  argumentos, delega para um handler.
- `handlers/record_handler.py` (`RecordCommandHandler`): orquestra o
  fluxo completo do MVP (inicializar → dispatch `StartCapture` →
  aguardar eventos/login → manter captura ativa, imprimindo status →
  aguardar Enter (`EnterKeyListener`) ou `KeyboardInterrupt` → dispatch
  `StopCapture` → aguardar exportação → exibir caminho da Base de
  Conhecimento).
- `handlers/enter_key_listener.py`: thread simples do próprio processo
  (não um daemon do sistema operacional) que aguarda Enter sem bloquear
  o laço de status.
- `handlers/pending.py`: mensagem padronizada para os comandos
  `status`/`validate`/`open`/`logs`/`config`, que dependem de módulos
  ainda não implementados (Session Manager, Export Engine, Log Engine,
  Configuration Manager) e por isso falham de forma limpa (exit code 1,
  sem traceback) em vez de fingir uma funcionalidade que não existe.
- `formatters/*.py`: funções puras que transformam estado/eventos em
  texto de terminal (substituindo a renderização de widgets).
- `bootstrap.create_controller() -> ApplicationControllerPort`: nova
  assinatura de `create_application() -> UserInterfacePort`, retornando
  o que a CLI realmente consome. Continua levantando
  `NotImplementedError` até que Browser Manager, Session Manager,
  Navigation Recorder, Element Recorder, Selector Analyzer, Screenshot
  Engine, Export Engine e Log Engine existam.
- Biblioteca `typer` adicionada (7 subcomandos com `--help` automático
  e validação por type hints); nenhuma outra dependência nova.

## Consequências

- `snkb --help`, `snkb version` e os 5 comandos "casca" funcionam hoje.
  `snkb record` executa até o ponto em que dependeria de um módulo
  central ainda não implementado, falhando com uma mensagem clara (não
  um traceback), exatamente como o projeto já se comportava com a GUI.
- Quando o Application Controller for implementado, a forma exata como
  ele notificará `RecordCommandHandler.handle_domain_event` (callback
  direto ou um Protocol de assinatura em `application/ports`) ainda
  precisa ser decidida — deliberadamente não especulado aqui.
- Testes de GUI com display real (`tests/integration/`) deixam de
  existir; em contrapartida, o fluxo de `snkb record` agora é 100%
  testável sem terminal ou display real, via `typer.testing.CliRunner`
  e um `ApplicationControllerPort` de teste.

## Rastreabilidade dos riscos residuais

Os itens listados em "Consequências" acima (comandos pendentes, wiring
do Application Controller) não ficam soltos: há um checklist acionável
por módulo — "isso desbloqueia qual comando da CLI, e em qual
arquivo" — em
[`docs/module-specs/README.md`](../module-specs/README.md#checklist-de-desbloqueio-na-cli-adr-0003).
Cada etapa futura do AI Development Guide (Browser Manager, Session
Manager, ...) deve marcar a linha correspondente ao concluir o módulo.
O prompt original que motivou este ADR está preservado em
[`docs/prompts/2026-07-16-code-review-cli-adequacao.md`](../prompts/2026-07-16-code-review-cli-adequacao.md).
