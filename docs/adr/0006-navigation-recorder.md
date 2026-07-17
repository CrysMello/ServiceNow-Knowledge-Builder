# ADR 0006 — Implementação do Navigation Recorder

## Status

Aceito — 2026-07-17.

## Contexto

Terceiro módulo central do projeto (Module Specifications, Capítulo 5;
AI Development Guide, etapa 6), depois do Browser Manager (ADR 0004) e
do Session Manager (ADR 0005). `NavigationRecorderPort` constrói e
expõe o grafo de navegação de uma sessão (`Page`, `NavigationEdge`),
mas todos os seus métodos são **síncronos** — nenhum é `async`. Isso é
um sinal de design importante: assim como o Session Manager, este
módulo não pode fazer I/O real (não pode chamar `page.title()` ou
inspecionar o DOM via Playwright), então ele não recebeu nenhuma
dependência do Browser Manager no construtor — só `EventPublisherPort`
e `LogEnginePort`, o mesmo padrão do Session Manager.

## Decisão

### Tradução "URL observada" → "grafo de navegação", sem I/O

`Browser Manager` já publica `PageChanged`/`UrlChanged` com `url: str`
e `tab_id: str` (ADR 0004) — dados simples, sem nenhum objeto
Playwright. O Navigation Recorder aprende sobre navegação
exclusivamente através de um novo método `observe_navigation(tab_id,
url, title=None)`, além da superfície mínima do Port (mesmo padrão de
"métodos extras" já usado no Session Manager, ADR 0005: o Protocol é o
contrato mínimo que o resto da aplicação pode assumir; a classe
concreta pode ser mais rica). O título é opcional porque os dois
eventos do Browser Manager não o carregam — quando o futuro
Application Controller tiver essa informação (por exemplo depois de
aguardar `page.title()` de forma assíncrona), poderá enviá-la tanto na
primeira chamada quanto depois, via uma nova chamada seguida de
`update_page()`.

`capture_page()` (zero argumentos, conforme o Port) opera sobre a
**última aba observada** (`observe_navigation()` mais recente),
espelhando o conceito de "página atual" único do Browser Manager
(`current_page()`, também singular). Ele:

1. Normaliza a URL (`urlparse`, minúsculas em esquema/host, remove
   fragmento — RS-005/RS-008 podem exigir sanitização adicional de
   parâmetros sensíveis no futuro; isso fica fora do escopo desta
   etapa e está registrado em "Consequências").
2. Calcula um `fingerprint` a partir de um hash SHA-256 da URL
   normalizada — não há inspeção de DOM real disponível, então a URL é
   o único sinal confiável para deduplicar páginas hoje (RN-006/
   RN-008: "identificada por URL, título ou fingerprint de DOM").
3. Se uma página com o mesmo fingerprint já existe, trata como
   revisita (atualiza `last_seen`/`title`, não cria uma nova `Page`);
   caso contrário, cria uma nova.
4. Se havia uma página "atual" anterior diferente da capturada agora,
   cria um `NavigationEdge` observado (`relation_type=OBSERVED`,
   `confidence=100`, já que a transição foi diretamente testemunhada
   via evento do Browser Manager, não inferida). `navigation_type` é
   sempre `MANUAL` nesta etapa — os eventos disponíveis não distinguem
   clique manual de redirecionamento/atualização/voltar/avançar (ver
   "Consequências").

### Detecção de redirecionamento via observações consecutivas

`RedirectDetected` (evento já existente em `navigation_events.py`) é
publicado quando `observe_navigation()` é chamado duas vezes para a
mesma aba sem uma `capture_page()` confirmando a primeira observação —
esse é o único sinal disponível de que uma URL mudou sozinha, sem uma
nova página sendo efetivamente capturada no meio. Uma cadeia de mais
de `max_redirect_chain` (padrão 10, parâmetro do construtor, não um
novo campo em `AppConfig` — não há evidência de que precise ser
configurável pelo usuário final ainda) observações consecutivas sem
captura levanta `RedirectLoopError` (5.16, "Redirecionamento
infinito"). Uma `capture_page()` bem-sucedida reinicia a contagem para
aquela aba.

### Quatro novas exceções em `navigation_exceptions.py`

Mudança aditiva, sem risco (mesmo padrão do `InvalidMetadataError` do
ADR 0005):

- `NavigationNotActiveError` — operação exige `start()` prévio.
- `NavigationAlreadyActiveError` — `start()` chamado duas vezes sem
  `stop()`/`clear_navigation()`.
- `NoPendingNavigationError` — `capture_page()` sem nenhuma
  `observe_navigation()` anterior.
- `PageNotFoundError` — `update_page()`/`close_page()` com um
  `page_id` nunca capturado nesta sessão.

### `stop()` não apaga o histórico; só `clear_navigation()` apaga

`stop()` marca a gravação como inativa (impede novas observações/
capturas) mas preserva `get_page_history()`/`get_navigation_graph()`/
`export_navigation()` — necessário para que a exportação final (Export
Engine, ainda não implementado) consiga ler os dados depois que a
gravação parou. `clear_navigation()` é a única operação que realmente
zera o estado interno, incluindo a associação com a sessão.

### `export_navigation()` monta o dict manualmente, mas é validado contra `NavigationJsonModel`

Em vez de depender de `pydantic` dentro de `modules/navigation` (que
deveria continuar livre de dependências de serialização), o método
monta um `dict[str, object]` simples, com os mesmos nomes de campo de
`shared.dtos.navigation_json.NavigationJsonModel`. Os testes garantem
que o resultado é aceito por `NavigationJsonModel(**exported)` sem
erros, então qualquer divergência de schema é pega imediatamente.

## Testes

`tests/unit/modules/navigation/test_navigation_recorder.py`: início/
fim de gravação (incluindo dupla partida rejeitada), captura de página
(criação, deduplicação por revisita, URL inválida), criação de aresta
observada entre duas páginas, detecção de redirecionamento e o limite
de cadeia, atualização de página com título tardio (bump de
`revision_id`), fechamento de página (limpa `current_page`), página/
aresta desconhecida, exportação validada contra `NavigationJsonModel`,
e reinício completo via `clear_navigation()`.

## Consequências

- `snkb record`: o contador "Páginas" ainda não reflete navegação real
  — falta o Application Controller encaminhar `PageChanged`/
  `UrlChanged` do Browser Manager para `observe_navigation()` +
  `capture_page()` (ver checklist em `docs/module-specs/README.md`).
- `navigation_type` sempre `MANUAL` é uma simplificação honesta, não
  uma classificação real. Quando o Browser Manager (ou o Application
  Controller) tiver sinal suficiente para distinguir back/forward/
  refresh/popup/nova aba, este módulo deve ganhar um parâmetro
  correspondente em `observe_navigation()` — não antes, para não
  inventar uma fonte de dado que não existe hoje.
- A normalização de URL é mínima (minúsculas + remoção de fragmento).
  Sanitização de parâmetros sensíveis (RS-005/RS-008) não foi
  implementada aqui por falta de especificação textual confirmada;
  fica registrada como pendência para quando o texto completo do
  Capítulo 5 estiver disponível para revisão.
- Element Recorder e Screenshot Engine (futuros) poderão associar seus
  artefatos a `page_id` sem nenhuma mudança neste módulo.
