# ADR 0005 — Implementação do Session Manager

## Status

Aceito — 2026-07-16.

## Contexto

Segundo módulo central do projeto (Module Specifications, Capítulo 4;
AI Development Guide, etapa 5), depois do Browser Manager (ADR 0004).
Diferente do Browser Manager, o Session Manager não faz nenhum I/O:
não importa Playwright, sistema de arquivos ou biblioteca de logging
concreta — é responsável apenas por manter e validar o ciclo de vida
administrativo de uma sessão de gravação (a entidade `Session`,
`domain.entities.session`), algo que a própria entidade já documentava
("The Session Manager is the only module authorized to hold a mutable
reference to this entity", 4.16). Por isso a implementação concreta
vive em `modules/session/`, não em `infrastructure/` — não há
biblioteca de terceiros para isolar (PW-001 não se aplica aqui).

## Decisão

### Um único arquivo, sem dependências de I/O

`modules/session/session_manager.py` define `SessionManager`,
implementando `SessionManagerPort` por completo. O construtor recebe
apenas `EventPublisherPort` e `LogEnginePort` (mesmo padrão de injeção
de dependência do Browser Manager), mais `now`/`generate_session_id`
opcionais para tornar os testes determinísticos (sem `datetime.now()`
nem `uuid4()` reais nos testes). Nenhuma dependência do Browser Manager
foi adicionada ao construtor: a coleta de metadados que exigiria
inspecionar o navegador (versão do browser, SO, resolução, idioma,
versão do ServiceNow, usuário autenticado) fica a cargo de quem
orquestra a gravação (futuro Application Controller), que deve chamar
`update_metadata()` — método que já existe no Port exatamente para
isso — em vez do Session Manager tentar extrair esses dados sozinho.
Evita-se assim inventar heurísticas de parsing (user agent, SO, versão
do ServiceNow) sem respaldo textual da especificação.

### Máquina de estados completa, além da superfície mínima do Port

`SessionManagerPort` expõe só 6 métodos de transição
(`create_session`, `start_session`, `pause_session`, `resume_session`,
`finish_session`, `cancel_session`), mas `SessionStatus` (SRS 9.4)
define 12 estados, incluindo `preparing`, `waiting_authentication`,
`ready` e `finalizing`, que nenhum desses 6 métodos alcança
diretamente. Como a entidade `Session` já documenta que o Session
Manager é o único dono de toda a máquina de estados, a classe concreta
expõe métodos adicionais, além do que o Protocol exige (o Protocol é o
contrato mínimo que o restante da aplicação pode assumir; a classe
concreta pode — e aqui deve — ser mais rica):

- `mark_preparing`, `mark_waiting_authentication`, `mark_ready` —
  progressão linear `created → preparing → waiting_authentication →
  ready`, percorrida pelo futuro Application Controller enquanto o
  Browser Manager inicializa e aguarda o login manual.
- `expire_session` — autenticação ServiceNow expirou em meio à
  gravação; publica `SessionExpired`.
- `timeout_session` — a sessão ficou tempo demais em `preparing`/
  `waiting_authentication` sem progredir; publica `SessionTimeout`.
- `recover_session` — marca uma sessão `interrupted` como `recovered`
  (RF-034, comando `RecoverInterruptedSession`), permitindo que
  `start_session` a retome depois.

Todas as transições passam por um único método privado `_transition`,
que valida a origem contra um conjunto de estados permitidos e levanta
`InvalidSessionTransitionError` caso contrário — nenhuma transição é
aceita implicitamente.

### `cancel_session` publica `SessionFailed`

Não existe um evento `SessionCancelled` dedicado em
`domain.events.session_events` — apenas `SessionFailed(reason: str)`.
Em vez de inventar um novo tipo de evento, `cancel_session` reutiliza
`SessionFailed` com `reason="Sessão cancelada pelo usuário."`,
tratando-o como o evento genérico de "sessão encerrada de forma
anormal", diferenciado do resultado (`interrupted` vs. `failed`) pelo
`status` da própria entidade, não pelo tipo do evento.

### `finish_session` decide `completed` vs. `completed_with_warnings`

A transição por `finalizing` é sempre instantânea (não há um segundo
método de Port para "confirmar" a finalização) e resolve
automaticamente para `completed_with_warnings` quando
`session.warnings` não está vazio, ou `completed` caso contrário — o
relógio injetado (`now`) é consultado uma única vez para
`recording_end`, mantendo a duração (`Session.duration_seconds`)
consistente.

### `get_statistics` não fabrica contadores

O Port exige `get_statistics(session_id) -> dict[str, object]`, mas a
entidade `Session` não tem campos de contagem de páginas/elementos/
screenshots — esses dados pertencem aos módulos que ainda vão
produzi-los (Navigation Recorder, Element Recorder, Screenshot
Engine), nenhum implementado ainda. Retornar zeros fixos seria
enganoso (pareceria dado real). A implementação atual retorna apenas o
que é genuinamente derivável da entidade: `status`, `created_at`,
`recording_start`, `recording_end`, `duration_seconds` e
`warnings_count`. Quando os módulos produtores existirem, este método
será revisitado (ver "Consequências").

### Novo `InvalidMetadataError`

`update_metadata()` precisava rejeitar chaves desconhecidas (proteção
contra erro do chamador, ex.: tentar sobrescrever `session_id` ou
`status` por fora da máquina de estados) sem usar um `ValueError`
solto, que violaria a regra de que toda exceção lançada por código
`snkb` deriva de `KnowledgeBuilderError`. Foi adicionado
`InvalidMetadataError` a `domain.exceptions.session_exceptions` — mudança
aditiva, sem risco, seguindo o mesmo padrão do `tab_id` aditivo do ADR
0004.

## Testes

`tests/unit/modules/session/test_session_manager.py`: cobre o ciclo de
vida completo (criação → preparing → waiting_authentication → ready →
recording → paused → recording → finalizing → completed/
completed_with_warnings), cancelamento a partir de múltiplos estados,
expiração, timeout (incluindo rejeição depois que a gravação já
começou), recuperação de sessão interrompida, todas as transições
inválidas relevantes, operações sobre sessão inexistente
(`SessionNotActiveError`), estatísticas e atualização de metadados
(incluindo rejeição de campo desconhecido). Sem duplos de teste
complexos — como o módulo não faz I/O, os testes usam apenas
`EventPublisherPort`/`LogEnginePort` gravadores simples, iguais aos já
usados em `test_browser_manager.py`.

## Consequências

- `snkb status` ainda não funciona ponta a ponta: falta o Application
  Controller para instanciar `SessionManager` e conectá-lo a
  `bootstrap.create_controller`, e para chamar `update_metadata()` com
  dados reais do navegador (ver checklist em
  `docs/module-specs/README.md`).
- `get_statistics()` será estendido (ou complementado por um
  agregador separado) quando Navigation Recorder, Element Recorder e
  Screenshot Engine existirem e precisarem expor contadores reais.
- `mark_preparing`/`mark_waiting_authentication`/`mark_ready` só serão
  efetivamente chamados quando o Application Controller orquestrar o
  Browser Manager e o Session Manager juntos — hoje ambos os módulos
  existem e funcionam isoladamente, mas nada ainda os conecta.
