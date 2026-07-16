# ADR 0002 — Implementação do UI Manager

## Status

**Superseded by [ADR 0003](0003-cli-presentation-layer.md)** —
2026-07-16. O produto passou a ser usado via terminal; o CustomTkinter
descrito abaixo foi removido. Este documento é preservado como registro
histórico da decisão original — não reescreva nem apague o conteúdo
abaixo.

~~Aceito — 2026-07-16.~~

## Contexto

O ADR 0001 deixou apenas a estrutura arquitetural pronta, sem nenhum
módulo implementado. Este ADR registra a primeira implementação real:
o **UI Manager** (Module Specifications, Capítulo 2), etapa 3 do AI
Development Guide.

O UI Manager é puramente a camada de apresentação: não conhece
Playwright, ServiceNow, seletores ou exportação de arquivos (2.4). Toda
comunicação com o restante do sistema ocorre através de
`ApplicationControllerPort` (ARQ-002), cuja implementação concreta
ainda não existe — por isso `bootstrap.create_application()` continua
levantando `NotImplementedError`, agora com uma mensagem que reflete
que apenas o UI Manager está pronto.

## Decisão

### Lacunas de contrato preenchidas antes da implementação

Ao revisar o contrato documentado do UI Manager (2.6, 2.12, 2.13),
duas peças previstas no scaffold original estavam faltando e foram
adicionadas:

- `snkb.domain.events.system_events.ErrorOccurred` — o evento
  `ERROR_OCCURRED` que a seção 2.13 lista como consumido pelo UI
  Manager não pertence a nenhum módulo específico (é publicado por
  "qualquer componente"), então foi criado como um evento transversal
  em `domain/events`, não dentro de um módulo.
- `OpenExportFolder` e `ShowReport` em
  `application.commands.commands` — os comandos `OPEN_EXPORT_FOLDER` e
  `SHOW_REPORT` da seção 2.12 ainda não existiam.

### Separação entre lógica pura e widgets

Para manter a regra "nenhuma regra de negócio na UI" (2.1) e permitir
testes automatizados sem depender de um display gráfico (PR-006), a
implementação foi dividida em:

| Arquivo | Responsabilidade | Depende de CustomTkinter? |
| --- | --- | --- |
| `presentation/state.py` | Enum `UiState` (2.8, 2.11) | Não |
| `presentation/view_models.py` | Dados de exibição dos painéis (2.9) | Não |
| `presentation/ui_event_queue.py` | Fila thread-safe evento→UI (ASY-006) | Não |
| `presentation/state_machine.py` | Transições de estado a partir de eventos consumidos | Não |
| `presentation/status_aggregator.py` | Contadores do Painel de Status | Não |
| `presentation/main_window.py` | Widgets, botões, renderização | Sim |
| `presentation/contracts.py` | `UserInterfacePort` (Protocol) | Não |

Essa divisão permite testar unitariamente a máquina de estados e os
contadores sem abrir nenhuma janela (`tests/unit/presentation/`), e
reserva um único teste de fumaça real (`tests/integration/
test_main_window_smoke.py`) para validar a construção efetiva dos
widgets — pulado automaticamente se não houver display disponível.

### `presentation/__init__.py` não reexporta a classe concreta

`CustomTkinterUserInterface` não é reexportada em
`presentation/__init__.py` de propósito: isso evitaria que qualquer
import de `snkb.presentation.contracts` (por exemplo, feito por
`bootstrap.py` só para tipar `ApplicationControllerPort`) forçasse a
importação do CustomTkinter. O import explícito
(`from snkb.presentation.main_window import CustomTkinterUserInterface`)
é exigido de quem realmente precisa da implementação concreta —
hoje, apenas o futuro composition root.

### Mensagens obrigatórias e segurança

As mensagens obrigatórias da interface (SRS, seção 11.1) foram
mapeadas para os estados correspondentes em `_status_message()`, e a
mensagem "Nenhuma credencial foi armazenada." é exibida permanentemente
no rodapé da janela. O painel de eventos exibe apenas o nome da classe
de cada evento (nunca seus campos), para nunca vazar um valor sensível
que um produtor futuro venha a colocar em um campo livre como `reason`
(2.16).

### O que ainda não existe

Nenhum `ApplicationControllerPort` concreto foi criado. O botão
"Sobre" é a única ação puramente local (não despacha comando, pois não
faz parte do catálogo documentado). Os contadores de elementos,
screenshots e logs no Painel de Status permanecem em zero até que o
Element Recorder, o Screenshot Engine e o Log Engine publiquem eventos
que o UI Manager possa consumir — mostrar um valor não derivado de um
evento real seria inventar dado, o que viola 2.4.

## Consequências

- O UI Manager pode ser executado isoladamente (com um
  `ApplicationControllerPort` de teste/duplo) assim que qualquer
  desenvolvedor quiser inspecionar a interface visualmente.
- A próxima etapa (Browser Manager, etapa 4 do AI Development Guide)
  não precisa alterar nada aqui: basta que o futuro
  `ApplicationControllerPort` concreto chame
  `ui.handle_domain_event(...)` sempre que publicar um evento de
  domínio relevante.
