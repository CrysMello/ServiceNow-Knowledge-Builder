# ADR 0013 — Browser Data Collector

## Status

Aceito — 2026-07-17.

## Contexto

O ADR 0012 conectou os oito módulos centrais através do
`ApplicationController`, mas deixou uma lacuna explícita registrada em
suas "Consequências": Element Recorder, Selector Analyzer e Screenshot
Engine eram instanciados e injetados no Export Engine, mas **nada os
alimentava** com dados reais — apenas o Navigation Recorder recebia
eventos (`PageChanged` → `observe_navigation`/`capture_page`). Como
consequência direta, nenhum mecanismo chamava
`SessionManager.update_metadata()` com os metadados de navegador que
`ExportEngine.export_session()` exige (ADR 0010), e a exportação real
**sempre falhava**.

Este ADR implementa o **Browser Data Collector**: um adaptador de
infraestrutura que observa o navegador real (Playwright) e alimenta
Element Recorder, Selector Analyzer e Screenshot Engine com dados
reais, fechando o pipeline ponta a ponta. Nenhum módulo já correto foi
reescrito — Browser Manager, Session Manager (só ganhou uma chamada
nova a `update_metadata`), Navigation Recorder (só ganhou um acessor
novo), Element Recorder, Selector Analyzer, Screenshot Engine e Export
Engine permanecem exatamente como estavam nos ADRs 0004–0011.

## Decisão

### Novo Port `BrowserDataCollectorPort`, com um retorno honesto sobre deduplicação

```python
class BrowserDataCollectorPort(Protocol):
    async def start(self, session_id: UUID) -> None: ...
    async def capture_current_page(self) -> PageCaptureResult | None: ...
    async def stop(self) -> None: ...
```

`capture_current_page()` retorna `PageCaptureResult | None` — não
sempre um resultado. A deduplicação (ver adiante) pode legitimamente
não ter nada novo a reportar; inventar um resultado nesse caso mentiria
sobre o que foi capturado, o mesmo princípio já seguido em todo o
projeto (ex.: `SelectorAnalyzerPort.get_best_selector() ->
SelectorCandidate | None`). `PageCaptureResult` é um resumo (`session_id`,
`page_id`, `url`, `title`, `element_count`, `new_element_count`,
`screenshot_id`, `captured_at`, `warnings`) — nunca duplica os dados
completos de `Page`/`Element`, que continuam vivendo nos módulos que já
os possuem.

Nova exceção `domain/exceptions/collector_exceptions.py`:
`CollectorNotActiveError`, levantada por `capture_current_page()`/
`stop()` chamados sem `start()` prévio.

### Implementação concreta em `infrastructure/browser/`

`BrowserDataCollector` vive em `infrastructure/browser/`, ao lado do
Browser Manager — o único outro módulo autorizado a importar
`playwright.async_api` (PW-001). Recebe no construtor o
`BrowserManagerPort` **da própria sessão** (para chamar
`current_page()`, que devolve `object` por design — PW-006) e as
instâncias/Ports já existentes de Navigation Recorder, Element
Recorder, Selector Analyzer, Screenshot Engine, Session Manager, o
`InMemoryEventBus` compartilhado, `LogEnginePort`, um
`InMemoryScreenshotStore` e `AppConfig`. Internamente, o objeto
devolvido por `current_page()` é tratado como `playwright.async_api.
Page` via `cast()` — seguro porque essa suposição já vale para todo o
resto de `infrastructure/browser/`; a aplicação/domínio nunca veem esse
tipo.

### Estabilidade de página: debounce por aba, nunca `networkidle`

`start()` assina `_on_domain_event` no mesmo `InMemoryEventBus`
(reaproveitado, não recriado). A cada `PageChanged` da sessão, agenda
(`loop.create_task`) uma tarefa de debounce por `tab_id`; um novo
`PageChanged` na mesma aba cancela a tarefa pendente e reagenda —
debounce clássico, nunca espera pelo evento `networkidle` do Playwright
(que pode nunca disparar em aplicações modernas). Dois campos novos em
`CapturePolicyModel` (`shared/dtos/app_config.py`, mudança aditiva):
`page_stability_seconds: float = 1.0` (janela de debounce) e
`page_stability_max_wait_seconds: float = 5.0` (teto absoluto e
determinístico). Um terceiro campo, `max_elements_per_page: int = 500`,
limita o DOM coletado por página.

### Deduplicação por fingerprint de conteúdo

Antes de reprocessar, `BrowserDataCollector` calcula `sha256(url +
assinatura ordenada dos elementos brutos coletados)` e compara com a
última assinatura bem-sucedida daquele `page_id` (dicionário em
memória, por instância do coletor — uma por sessão). Se idêntica, não
chama `observe_elements`/`stage_capture` de novo, e
`capture_current_page()` devolve `None`.

### Coleta de DOM: um `page.evaluate()`/`frame.evaluate()` por frame

Um único snippet JavaScript (constante do módulo) roda via
`page.evaluate()` no frame principal e via `frame.evaluate()` em cada
`page.frames` secundário — cada chamada isolada em seu próprio
`try/except`: uma falha em um frame não aborta os demais, e é registrada
como aviso (`PageCaptureResult.warnings`), nunca cancela a sessão
inteira. Seleciona apenas `button, input, select, textarea, a, [role],
[aria-label], [data-testid], [onclick], [tabindex]`, capado em
`max_elements_per_page` — nunca o DOM completo (RS-002). Para cada
elemento, coleta `tag`, `role`, tipo de campo, nome acessível
(aria-label → aria-labelledby resolvido → texto do próprio elemento —
aproximação documentada, não o algoritmo completo do W3C), rótulo
(`<label for>`/label ancestral), placeholder, `id`, `name`, classes,
`required`/`readonly`/`disabled`, visibilidade (via
`getBoundingClientRect`), uma heurística conservadora de campo sensível
(`is_sensitive_hint`, baseada em `id`/`name`/`autocomplete` contendo
"password"/"senha"/"cpf"/"ssn") e o índice do ancestral mais próximo no
mesmo lote (`parent_index`).

**Nenhum valor de campo é coletado** — desvio deliberado do exemplo de
referência do pedido original (que sugeria "valor"): a entidade
`Element`/`RawElementObservation` não tem esse campo (ADR 0007, decisão
já tomada), e coletar um valor real de formulário contrariaria RS-002.

**`data-testid` não é mapeado para um candidato de seletor** — gap já
documentado na ADR 0008 ("nenhum candidato `DATA_TESTID` é gerado").
Fechar essa lacuna exigiria alterar `Element`, `RawElementObservation`,
`SelectorAnalyzer` e o schema `page_json.py` — módulos já corretos e
testados, fora do escopo deste ADR. O atributo é lido pelo script JS mas
descartado no lado Python, e a limitação é registrada aqui, não
escondida.

Os dados convertidos viram `RawElementObservation` (reaproveitado sem
alteração) e são entregues via `element_recorder.observe_elements(...)`
+ `capture_elements(page_id)`, usando o `page_id` que o Navigation
Recorder **já** atribuiu à página atual
(`navigation_recorder.get_current_page()`) — garante a mesma associação
sessão/página/elemento em todo o pipeline.

### Selector Analyzer e Screenshot Engine: alimentados, não reimplementados

Para cada elemento novo, o coletor chama
`selector_analyzer.register_session_for_page(...)` (idempotente) +
`analyze(element_id)` — cada chamada em seu próprio `try/except`, para
que um elemento problemático não aborte os demais. Nenhuma regra de
pontuação de seletor é tocada.

Após a coleta de elementos, `await page.screenshot(type="png",
full_page=...)` uma vez por captura estável (respeitando
`full_page_screenshots` já existente em `CapturePolicyModel`);
dimensões vêm de `page.viewport_size` (fallback para
`AppConfig.resolution_*`). `screenshot_engine.stage_capture(...)` +
`capture_page(page_id)` devolvem o `Screenshot` com `screenshot_id`; os
bytes reais são guardados em um novo `InMemoryScreenshotStore`
(`application/services/application_controller.py`, ao lado de
`InMemoryEventBus`) — construído uma única vez em `bootstrap.py` e
injetado tanto no `ExportEngine` (`screenshot_bytes_provider=store.get`)
quanto na fábrica do coletor (`store.put`). Fecha exatamente a lacuna
que as ADRs 0009/0010 já documentavam ("nada fornece bytes reais").

### Metadados de sessão: fecha o bloqueio de exportação

Em `start()`, o coletor lê o que só a infraestrutura pode saber e chama
**uma vez** `session_manager.update_metadata(session_id, {...})`:
`browser="Chromium"`, `browser_version` (via
`page.context.browser.version`, propriedade síncrona real do
Playwright, com *fallback* para `"unknown"`), `operating_system`
(`platform.system()`/`platform.release()`, biblioteca padrão — não
depende do navegador), `screen_resolution`/`viewport` (de
`AppConfig.resolution_width/height`, já conhecidos desde o início da
sessão). Confirmado pelo teste de integração com Chromium real: depois
desta chamada, `export_engine.validate(session_id)` passa a retornar
`True` — a exportação real deixa de falhar.

### `ApplicationController`: fábrica opcional + ordem de encerramento revisada

Novo parâmetro opcional no construtor,
`browser_data_collector_factory: Callable[[BrowserManagerPort],
BrowserDataCollectorPort] | None = None` (mesmo padrão de
`browser_manager_factory`; `None` preserva compatibilidade retroativa
com quem já construía `ApplicationController` sem coletor). Em
`_run_capture_flow`, logo após `_capture_last_known_page`, se a fábrica
existir: `collector.start(session_id)` seguido de uma captura explícita
da página inicial (`collector.capture_current_page()`, dentro de
`contextlib.suppress(Exception)` — mesma tolerância já aplicada ao
resto do fluxo de inicialização).

**Ordem de encerramento ajustada**: no `finally` de
`_run_capture_flow`, `await collector.stop()` roda **antes** de `await
browser_manager.shutdown()` — uma captura/screenshot final só é
possível com o navegador ainda vivo. `stop()` cancela e aguarda
(`asyncio.gather(..., return_exceptions=True)`) todas as tarefas de
debounce pendentes, tenta uma última `capture_current_page()` **antes**
de se marcar inativo (bug encontrado e corrigido pelo próprio teste
unitário `test_stop_awaits_pending_capture_task`: marcar `_active =
False` cedo demais fazia a última captura ser silenciosamente
descartada por `CollectorNotActiveError`, engolida pelo `suppress`
ao redor). O restante do fluxo de `_handle_stop_capture` (parar
Navigation Recorder, finalizar sessão, exportar) continua depois que a
thread em segundo plano já terminou (`join`), como no ADR 0012.
`_on_domain_event` (ligação `PageChanged` → Navigation Recorder) não
muda — o coletor se assina ao mesmo barramento de forma independente,
dentro de sua própria `start()`.

### `bootstrap.py`: fiação do novo módulo

Constrói `InMemoryScreenshotStore` junto do `event_bus`; passa
`screenshot_bytes_provider=screenshot_store.get` ao `ExportEngine`
(único campo novo preenchido); define `browser_data_collector_factory`
fechando sobre `navigation_recorder`, `element_recorder`,
`selector_analyzer`, `screenshot_engine`, `session_manager`,
`event_bus`, `log_engine`, `screenshot_store`, `config` — mesmo padrão
de `browser_manager_factory`.

## Frames/iframes e Shadow DOM (limitações conhecidas)

- Frame principal e frames secundários acessíveis (`page.frames`) são
  coletados; um frame inacessível (fechado, cross-origin bloqueado,
  etc.) gera um aviso e é ignorado, sem abortar a captura da página.
- `frame_selector` é melhor-esforço, baseado em `iframe[name='...']`
  quando o frame tem `name` — não é um caminho CSS computado até o
  elemento `<iframe>` real. Suficiente para o MVP, registrado como
  limitação.
- Shadow DOM não é atravessado — o `querySelectorAll` do script de
  coleta não entra em `shadowRoot`s. Fora do escopo do MVP, como
  antecipado pelo pedido original.

## Testes

`tests/unit/infrastructure/browser/test_browser_data_collector.py`
(16 cenários, com duplos de Playwright falsos, sem navegador real):
`start`/`stop` sem sessão ativa levantam `CollectorNotActiveError`;
`start()` coleta metadados de sessão; `start()` duas vezes é idempotente;
captura normaliza elementos reais; publica eventos a jusante (Element
Recorder/Selector Analyzer/Screenshot Engine); bytes de screenshot
chegam ao `InMemoryScreenshotStore`; deduplica conteúdo idêntico;
reprocessa quando o conteúdo muda; erro de coleta de DOM é reportado
sem derrubar a sessão; erro de screenshot não impede a captura de
elementos; página parcialmente carregada ainda é capturada com aviso;
frame inacessível não aborta a captura inteira; captura sem página
disponível devolve `None`; navegações rápidas em sequência forçam uma
captura dentro do teto máximo de espera; `stop()` aguarda uma tarefa de
captura pendente.

`tests/integration/test_browser_data_collector_integration.py`: Chromium
real (headless), servidor HTTP local com três elementos conhecidos
(`button`, `input`, `a`). Valida os 3 elementos coletados e
normalizados, seletores gerados para todos, um screenshot real
capturado e armazenado, e — critério decisivo — `export_engine.
export(session_id)` seguido de `export_engine.validate(session_id) is
True`, com `session.json`/`selectors.json`/`pages/*.json`/
`screenshots/*.png` reais em disco.

`tests/integration/test_application_controller_integration.py`:
atualizado para fiar o coletor (antes só validava que a exportação
falhava de forma honesta, exatamente como o ADR 0012 documentava). Agora
valida que `ExportCompleted` é publicado, `ExportFailed` não, e que os
artefatos exportados existem e não estão vazios.

`tests/acceptance/test_local_recording_flow.py`: um app HTML local
determinístico de quatro páginas (login simulado, home, lista de planos
de teste, formulário de cadastro), Chromium real, sem depender da
internet, do Microsoft SSO ou de uma instância real do ServiceNow.
Orquestra os módulos diretamente (mesmo padrão do teste de integração
do coletor) através das quatro páginas, navegando via `page.goto()` —
simulação determinística de navegação em uma página estática sob
controle do próprio teste, não automação de uma ação de negócio do
ServiceNow. Valida 4 páginas capturadas, elementos e seletores reais
por página, e a Base de Conhecimento completa exportada com sucesso.

`tests/contract/test_ports.py`: `BrowserDataCollectorPort` expõe
exatamente `start`/`capture_current_page`/`stop`.

## Consequências

- **A exportação real deixa de falhar por padrão**: com o Browser Data
  Collector fiado (via `bootstrap.create_controller`), `snkb record`
  agora produz metadados de sessão completos, elementos reais,
  seletores reais e screenshots reais — confirmado por três níveis de
  teste (unitário com duplos, integração com Chromium real, e aceite
  com um app local de quatro páginas).
- `data-testid` continua sem um candidato de seletor dedicado (ADR
  0008) e o caminho CSS computado até um `<iframe>` continua
  melhor-esforço, não exato — limitações conhecidas, não silenciosas.
- Shadow DOM não é coletado — item explicitamente fora do MVP.
- `snkb status`/`validate`/`open`/`logs`/`config` continuam pendentes,
  pelos mesmos motivos já registrados no ADR 0012 (descoberta de sessão
  em disco e Configuration Manager, nenhum dos dois no escopo deste
  ADR).
