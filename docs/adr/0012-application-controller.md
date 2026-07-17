# ADR 0012 — Implementação do Application Controller

## Status

Aceito — 2026-07-17.

## Contexto

Último item do composition root (Module Specifications 2.5, ARQ-002;
AI Development Guide, etapa final), depois de todos os oito módulos
centrais dos Capítulos 3–10 (Browser Manager, Session Manager,
Navigation Recorder, Element Recorder, Selector Analyzer, Screenshot
Engine, Export Engine, Log Engine — ADRs 0004 a 0011). Até aqui, cada
módulo era testado isoladamente, sem nenhum outro módulo realmente
instanciando ou chamando os demais. Este ADR documenta o
`ApplicationController`: a peça que finalmente conecta todos eles,
substitui o `NotImplementedError` incondicional de
`bootstrap.create_controller`, e resolve a decisão explicitamente
adiada no ADR 0003 ("como eventos chegam a
`RecordCommandHandler.handle_domain_event`: callback direto vs.
Protocol de assinatura").

## Decisão

### `subscribe()` foi adicionado a `ApplicationControllerPort`

Diferente de todos os métodos "extras" adicionados às classes
concretas dos módulos anteriores (que ficaram de fora dos Ports
porque só o futuro Application Controller precisava deles), aqui a
resposta é diferente: quem precisa assinar eventos é a própria camada
de apresentação (`presentation/cli/commands/record.py`), que só pode
depender do Port, nunca de uma classe concreta (ARQ-002). Por isso
`subscribe(handler: Callable[[DomainEvent], None]) -> None` foi
adicionado diretamente ao `ApplicationControllerPort` — a decisão que
o ADR 0003 deliberadamente adiou. `record.py` agora chama
`controller.subscribe(handler.handle_domain_event)` antes de
`handler.run(...)`.

### Um barramento de eventos em memória compartilhado (`InMemoryEventBus`)

Todos os seis módulos que publicam eventos consumidos pela CLI —
Session Manager (`SessionCreated`/`SessionStarted`/...), Navigation
Recorder (`NavigationStarted`/`PageCaptured`/...), Export Engine
(`ExportStarted`/`ExportCompleted`/`ExportFailed`/...) e, por sessão,
o Browser Manager (`BrowserStarted`/`LoginDetected`/`PageChanged`/...)
— recebem a **mesma instância** de `InMemoryEventBus` como seu
`EventPublisherPort`. `bootstrap.py` a constrói uma única vez e a
injeta em todos eles; o `ApplicationController` a recebe pronta (não a
constrói sozinho) para que `bootstrap.py` possa compartilhá-la
livremente. Implementa exatamente o contrato já documentado em
`EventPublisherPort`: um erro em um assinante nunca impede que os
demais recebam o evento (AI Coding Standards, seção 12) — a exceção é
registrada via `LogEnginePort.exception()` e o laço de assinantes
continua.

### Uma instância de Browser Manager por sessão, via fábrica

Diferente dos outros seis módulos (construídos uma única vez, vivendo
pela duração do processo), o Browser Manager precisa de um
`session_id` já no construtor (ADR 0004: "nunca reutilizar contexto
anterior"). `bootstrap.py` monta uma função fábrica
(`browser_manager_factory: Callable[[UUID, EventPublisherPort,
LogEnginePort], BrowserManagerPort]`) fechando sobre a `AppConfig` já
carregada; o `ApplicationController` a chama uma vez por
`StartCapture`, nunca importando `PlaywrightBrowserManager`
diretamente (preserva ARQ-001: `application/` não conhece
infraestrutura concreta).

### Ponte entre o laço assíncrono do Playwright e o `dispatch()` síncrono da CLI

`RecordCommandHandler.run()` (CLI) é síncrono e espera que
`dispatch(StartCapture(...))` retorne quase imediatamente, para então
entrar em seu próprio laço de polling. Mas o Browser Manager é
inteiramente assíncrono (`await initialize()`, `await wait_login()`,
...). A solução: `_handle_start_capture` cria a sessão de forma
síncrona (rápido, sem I/O) e delega o resto — inicializar o navegador,
abrir a URL, aguardar o login, iniciar a gravação — para uma
`asyncio.Event`/`asyncio.AbstractEventLoop` rodando em uma **thread
real separada** (`threading.Thread(daemon=True)`, injetável via
`thread_factory` para testes). Uma vez que o login é detectado e
`navigation_recorder.start(session_id)` roda, a coroutine permanece
viva aguardando um sinal de parada (`await stop_event.wait()`) — é
esse "aguardar indefinidamente" que mantém o loop de eventos do
Playwright rodando, permitindo que `PageChanged`/`UrlChanged`/
`TabCreated`/`TabClosed` continuem disparando enquanto o usuário
navega.

`StopCapture`, ao contrário, é deliberadamente **bloqueante**: sinaliza
a parada via `loop.call_soon_threadsafe(stop_event.set)`, espera a
thread encerrar (`thread.join(timeout=...)`, para garantir que o
navegador já foi desligado) e só então finaliza a sessão e exporta —
exatamente o que `RecordCommandHandler._finalize()` já esperava (ler
`ExportCompleted`/`ExportFailed` logo após despachar `StopCapture`).

### Corrida entre login e `StopCapture` (Ctrl+C durante o login)

Se o usuário interromper a gravação enquanto ainda aguarda o login
manual, `wait_login()` (que só termina quando o Browser Manager
detecta autenticação ou expira por timeout) não seria cancelado
sozinho. `_wait_for_login_or_stop()` resolve isso com
`asyncio.wait({login_task, stop_task}, return_when=FIRST_COMPLETED)`:
se o sinal de parada vence a corrida, a tarefa de login é cancelada e
a sessão nunca chega a `RECORDING` — apenas é cancelada
(`SessionManager.cancel_session`), sem tentar `navigation_recorder.
stop()`/`finish_session()`/exportar (que exigiriam um estado que nunca
foi alcançado).

### Falhas durante o início da captura publicam `ErrorOccurred` e cancelam a sessão

Qualquer exceção entre `mark_preparing` e `navigation_recorder.start`
(Chromium indisponível, timeout de login, etc.) é capturada dentro da
própria coroutine: publica `ErrorOccurred` (evento transversal já
existente, `domain.events.system_events`) e cancela a sessão. O
`finally` sempre tenta `browser_manager.shutdown()`, mesmo que a
inicialização tenha falhado — assim como o próprio Browser Manager já
tolera isso internamente (ADR 0004, PW-007).

### Apenas uma ligação automática entre módulos: `PageChanged` → Navigation Recorder

O `ApplicationController` se assina a si mesmo no barramento
(`_on_domain_event`) e, ao observar um `PageChanged` do Browser
Manager, chama `navigation_recorder.observe_navigation()` +
`capture_page()` — a única integração cross-módulo automática que
existe hoje. Element Recorder, Selector Analyzer e Screenshot Engine
são instanciados e injetados no Export Engine, mas **nada os
alimenta** com dados reais: isso exigiria um coletor assíncrono de DOM
(via Playwright, para `observe_elements()`) e capturas de tela reais
(`page.screenshot()`, para `stage_capture()`) — funcionalidades
distintas e substanciais, deliberadamente fora do escopo desta etapa
(ver "Consequências").

### A primeira navegação sempre acontece antes do login — e era perdida

Descoberto pelo teste de integração com Chromium real (não pelos
testes unitários, que usavam um Browser Manager falso "perfeito
demais"): a primeira navegação de uma sessão acontece dentro de
`open_url()`, publicando `PageChanged` **antes** de
`navigation_recorder.start()` (que só roda depois do login). Sem
tratamento, essa página inicial — normalmente a própria tela inicial
do ServiceNow após o login — nunca seria capturada, a menos que o
usuário navegasse para outra página depois. A correção:
`_on_domain_event` sempre guarda o `PageChanged` mais recente por
sessão em `_last_page_event` (mesmo com a gravação ainda inativa); assim
que `navigation_recorder.start()` roda, `_capture_last_known_page()`
reaplica esse evento guardado, capturando retroativamente a página em
que o usuário já estava. Depois disso, `_navigation_active_session_id`
passa a valer e novos `PageChanged` são processados ao vivo, como
antes.

### `bootstrap.py` ganhou um carregador de configuração mínimo — não um Configuration Manager

`create_controller()` precisa de uma `AppConfig` para existir. Como o
Configuration Manager (`ConfigurationProviderPort`,
`infrastructure/configuration/`) continua reservado — item **separado**
no checklist de `docs/module-specs/README.md`, nunca fez parte do
escopo dos Capítulos 3–10 — `bootstrap._load_config()` lê
`config/local.json` (se existir) ou `config/default.json` e valida via
`AppConfig.model_validate_json()`. Isso não substitui o Configuration
Manager: não há recarregamento em tempo de execução, nem mensagens de
erro por campo (CFG-006) — só o suficiente para o Application
Controller poder existir. `snkb config` continua chamando
`announce_pending`.

### `snkb status`/`validate`/`open`/`logs` continuam pendentes — por um motivo novo

Antes deste ADR, esses comandos estavam pendentes porque os módulos
dos quais dependiam não existiam. Agora todos existem e estão
conectados — mas os comandos **ainda não funcionam**, por um motivo
diferente e mais fundamental: cada invocação de `snkb <comando>` é um
**processo novo**. `SessionManager`/`NavigationRecorder`/etc. guardam
estado em memória, que não sobrevive ao fim do processo que gravou a
sessão. Consultar "a sessão mais recente" de um processo diferente
exige ler os artefatos já exportados em disco
(`session.json`/`manifest.json`), um mecanismo de descoberta que este
ADR não implementa (não é uma responsabilidade do Application
Controller em si, e sim de uma camada de leitura pós-exportação ainda
não projetada). Por isso `query(GetRecentSessions(...))` levanta
`NotImplementedError` explicitamente, em vez de fingir que funciona.

### Uma nova exceção: `CaptureAlreadyActiveError`

`domain.exceptions.application_exceptions` (novo arquivo, seguindo o
padrão de todos os módulos anteriores) — levantada quando
`StartCapture` é despachado enquanto outra sessão já está sendo
gravada (RN-005: uma gravação por vez).

## Testes

`tests/unit/application/services/test_application_controller.py`: usa
os seis módulos de dados **reais** (síncronos, sem I/O, já testados
isoladamente) e um Browser Manager **falso** controlável — o único
módulo que exigiria um Chromium de verdade. `dispatch(StartCapture)`
roda em uma thread real; os testes esperam a conclusão via polling
curto (nunca `sleep` fixo). Cobre: sessão criada e gravação alcançada,
dupla partida rejeitada, `PageChanged` publicado *antes* do login
sendo capturado retroativamente e *depois* do login sendo capturado ao
vivo (ambos pelo Navigation Recorder), falha durante a
inicialização (evento + cancelamento + navegador desligado),
encerramento normal (navegador desligado, exportação tentada e
falhando de forma honesta hoje), Ctrl+C durante o login (cancela sem
tentar gravar), pausar/retomar, `ExitApplication` (com e sem gravação
ativa), as quatro consultas (`GetSessionStatus`, `GetSessionStatistics`,
`GetNavigationTimeline`, `GetRecentSessions` → `NotImplementedError`),
comando/consulta desconhecidos, `subscribe()` recebendo eventos, e o
`InMemoryEventBus` isoladamente (erro em um assinante não afeta os
demais).

`tests/integration/test_application_controller_integration.py`: um
Chromium real (headless), com todos os módulos reais e um
`PlaywrightBrowserManager` real, navegando para um servidor HTTP local
(nunca a internet — AI Coding Standards, seção 19). Configura
`LoginDetectionPolicyModel` com limiares curtos para que a página local
(que obviamente não é um login Microsoft) seja aceita como "logada" em
poucos ciclos. Cobre o ciclo completo: sessão alcança `RECORDING`, pelo
menos uma página é capturada de verdade, e o encerramento chega a
`COMPLETED`/`COMPLETED_WITH_WARNINGS` mesmo com a exportação real
falhando (metadados ausentes). Pulado automaticamente se
`playwright install chromium` não tiver sido executado.

## Consequências

- **O que funciona ponta a ponta hoje** (com Chromium instalado e uma
  instância ServiceNow real): `snkb record --instance-url ...` abre o
  navegador, aguarda o login manual, marca a sessão como gravando,
  captura páginas conforme a navegação acontece, e ao pressionar Enter/
  Ctrl+C desliga o navegador e tenta exportar.
- **Exportação real sempre falha hoje**: nenhum mecanismo coleta
  `browser`/`browser_version`/`operating_system`/`screen_resolution`/
  `viewport` via `SessionManager.update_metadata()` — `export_session()`
  continua levantando `ExportValidationError` (ADR 0010) para toda
  sessão real. É o próximo passo concreto e bem delimitado, não uma
  reformulação arquitetural.
- **Element Recorder, Selector Analyzer e Screenshot Engine não
  recebem dados reais** — só o Navigation Recorder está de fato
  alimentado. Um futuro coletor assíncrono de DOM (para
  `observe_elements()`) e uma ponte para `page.screenshot()` (para
  `stage_capture()`) são funcionalidades distintas, não cobertas aqui.
- `snkb status`/`validate`/`open`/`logs`/`config` continuam chamando
  `announce_pending` — não por módulos ausentes, mas por dependerem de
  descoberta de sessão em disco (o primeiro trio) ou do Configuration
  Manager (o último), nenhum dos dois no escopo deste ADR.
- `navigation_type` continua sempre `MANUAL` (ADR 0006) e nenhum
  candidato `DATA_TESTID` é gerado (ADR 0008) — limitações herdadas,
  inalteradas por esta etapa.
