# ADR 0004 — Implementação do Browser Manager

## Status

Aceito — 2026-07-16.

## Contexto

Primeiro módulo central real do projeto (Module Specifications,
Capítulo 3; AI Development Guide, etapa 4). Até aqui, todos os módulos
centrais (Browser Manager, Session Manager, Navigation Recorder,
Element Recorder, Selector Analyzer, Screenshot Engine, Export Engine,
Log Engine) eram apenas pacotes reservados e ports (Protocols) sem
implementação. Este ADR documenta a primeira implementação concreta:
`infrastructure.browser.browser_manager.PlaywrightBrowserManager`,
implementando `BrowserManagerPort`.

O Browser Manager é responsável por: iniciar o Playwright/Chromium,
abrir a URL configurada, permitir que o usuário conclua o login manual
Microsoft e detectar quando isso aconteceu, monitorar abas e navegação,
e encerrar tudo com segurança — sem nunca preencher formulários,
clicar em elementos ou automatizar a autenticação (RS-001, RS-002,
PW-008).

## Decisão

### Estrutura de arquivos

`infrastructure/browser/` (único pacote autorizado a importar
`playwright`, PW-001) ganhou três arquivos:

- `browser_manager.py` — `PlaywrightBrowserManager`, a classe principal.
- `tab_tracker.py` — `TabTracker`/`TabRecord`: associa cada `Page` a um
  identificador estável e seus metadados (3.9), sem nunca expor o
  objeto `Page` fora da classe (PW-006).
- `login_detector.py` — `LoginDetector`: avalia se a autenticação
  Microsoft terminou, sem nunca preencher nada (RF-004, 3.3).

Cada peça é testável isoladamente com duplos de teste simples,
seguindo o mesmo padrão já usado no UI Manager/CLI (separar lógica pura
de I/O real).

### Detecção de login (RF-004) e nova configuração

RF-004 exige que a detecção de autenticação concluída dependa de **pelo
menos dois sinais configuráveis** (nunca um único seletor), porque
instâncias corporativas podem customizar suas páginas. Isso não existia
em nenhum lugar do schema de configuração ainda, então foi adicionado
`LoginDetectionPolicyModel` a `shared.dtos.app_config.AppConfig` (novo
campo `login_detection`, com o mesmo padrão de sub-modelo já usado por
`CapturePolicyModel`):

- `stability_seconds` — por quanto tempo os sinais devem permanecer
  verdadeiros antes de declarar sucesso (evita falsos positivos durante
  um redirecionamento passageiro).
- `poll_interval_seconds`, `timeout_seconds` — controle do laço de
  espera em `wait_login()`.
- `microsoft_login_hostnames` — hosts conhecidos do Entra ID/Microsoft
  Login, usados para o sinal "fora do login Microsoft".
- `service_now_marker_selector`, `expected_title_substring` — sinais
  opcionais adicionais, desligados por padrão.

Os sinais implementados são: domínio da URL corresponde à instância
configurada; URL não é uma página de login Microsoft conhecida;
(opcional) título contém o texto configurado; (opcional) elemento
marcador presente. `LoginDetector.is_authenticated()` retorna
`True` quando pelo menos 2 desses sinais são verdadeiros no instante
avaliado; a janela de estabilidade (esperar o resultado se manter) é
responsabilidade de `BrowserManager.wait_login()`, não do detector.

### Novo campo `tab_id` em `PageChanged`/`UrlChanged`

Os eventos `PageChanged` e `UrlChanged` (`domain.events.browser_events`)
ganharam um campo `tab_id: str`, ausente até então. Como nenhum
consumidor desses eventos existia ainda (Navigation Recorder não está
implementado), esta é uma mudança aditiva sem nenhum risco de quebra —
e é necessária para que o futuro Navigation Recorder saiba a qual aba
cada navegação pertence (3.9, "monitorar todas as abas abertas").

### Um `PlaywrightBrowserManager` por sessão

A classe recebe `session_id: UUID` no construtor (não em cada método) —
uma instância nova é criada por gravação, nunca reutilizada entre
sessões (RN-005, 3.7 "nunca reutilizar contexto anterior"). O
construtor não faz nenhum I/O (COD-007): só `initialize()` de fato
inicia o Playwright.

### `shutdown()` vs. `close()`

O Module Specifications 3.14 lista os dois métodos separadamente sem
detalhar a diferença. Adotado: `close()` libera todos os recursos do
Playwright de forma tolerante a falhas (PW-007 — tenta fechar
contexto, depois navegador, depois parar o Playwright, mesmo se um
deles falhar) e é reutilizado por `restart()`; `shutdown()` = `close()`
mais a publicação do evento `BrowserStopped`, para o caminho de
encerramento normal solicitado pelo Application Controller (RF-007).

### Desconexão inesperada

`Browser.on("disconnected", ...)` é observado para publicar
`BrowserCrashed` quando o navegador fecha fora do nosso próprio
`close()`/`shutdown()` (ER-011, 3.18). Uma flag interna (`_closing`)
distingue esse caso do encerramento esperado, evitando um
`BrowserCrashed` espúrio durante um `shutdown()` normal.

### Injeção de dependência para testes

O construtor aceita `start_playwright` (fábrica assíncrona do
Playwright) e `login_detector` opcionais, com os valores reais como
padrão. Isso permite testar toda a lógica de orquestração — publicação
de eventos, mapeamento de erros, rastreamento de abas — com duplos de
teste simples, sem precisar de um Chromium real na maioria dos testes.

## Testes

- `tests/unit/infrastructure/browser/test_tab_tracker.py` e
  `test_login_detector.py`: puros, sem Playwright.
- `tests/unit/infrastructure/browser/test_browser_manager.py`: toda a
  orquestração (inicialização, `open_url`, `wait_login`,
  `shutdown`/`close`/`restart`, rastreamento de abas, desconexão
  inesperada) com uma árvore de duplos de teste para
  Playwright/Browser/Context/Page — nenhum navegador real é aberto.
- `tests/integration/test_browser_manager_integration.py`: um Chromium
  real (headless), navegando para um servidor HTTP local
  (`127.0.0.1`, nunca a internet ou uma instância real — AI Coding
  Standards, seção 19), cobrindo o ciclo de vida completo. Pulado
  automaticamente se `playwright install chromium` não tiver sido
  executado.
- `pyproject.toml`: `asyncio_mode = "auto"` adicionado à configuração
  do pytest, já que a maior parte dos novos testes é assíncrona.

## Consequências

- `snkb record` ainda não funciona ponta a ponta: falta o Application
  Controller para de fato instanciar um `PlaywrightBrowserManager` e
  conectá-lo a `bootstrap.create_controller` (ver checklist em
  `docs/module-specs/README.md`). O `NotImplementedError` atual
  permanece correto e não foi alterado nesta etapa.
- Session Manager (próximo módulo) poderá consumir `LoginDetected`,
  `BrowserStarted` e os eventos de navegação sem nenhuma mudança no
  Browser Manager.
- Screenshot Engine e Navigation Recorder (futuros) usarão
  `current_page()`/`current_context()` para capturar evidências e
  mapear a navegação, respeitando PW-006 (nunca persistir o objeto
  `Page` em si).
