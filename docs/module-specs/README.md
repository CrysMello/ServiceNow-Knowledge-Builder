# Especificações de módulo

Coloque aqui o documento oficial de Module Specifications (e qualquer
adendo por módulo) à medida que for aprovado. Cada etapa de
implementação de módulo (AI Development Guide, etapas 4-11) deve citar
o capítulo e a seção do requisito que satisfaz, de acordo com a matriz
de rastreabilidade do Capítulo 14 do SRS.

Capítulos cobertos pelo documento de Module Specifications atual:

| Capítulo | Módulo               | Port em `application/ports`   | Status        |
| -------- | -------------------- | ------------------------------ | ------------- |
| 2        | UI Manager (substituído por CLI) | `presentation.cli.main` | Camada de apresentação é CLI, não GUI — ver ADR 0003 (supersede o ADR 0002) |
| 3        | Browser Manager        | `browser_manager_port`         | Implementado e ligado — `infrastructure.browser.browser_manager.PlaywrightBrowserManager` (ver ADR 0004), instanciado por sessão via `ApplicationController` (ADR 0012) |
| 4        | Session Manager        | `session_manager_port`         | Implementado e ligado — `modules.session.session_manager.SessionManager` (ver ADR 0005), conectado via `bootstrap.create_controller` (ADR 0012) |
| 5        | Navigation Recorder    | `navigation_recorder_port`     | Implementado e ligado — `modules.navigation.navigation_recorder.NavigationRecorder` (ver ADR 0006), conectado via `bootstrap.create_controller` (ADR 0012) |
| 6        | Element Recorder       | `element_recorder_port`        | Implementado e ligado — `modules.elements.element_recorder.ElementRecorder` (ver ADR 0007), alimentado com dados reais de DOM pelo Browser Data Collector (`infrastructure.browser.browser_data_collector.BrowserDataCollector`, ver ADR 0013) |
| 7        | Selector Analyzer      | `selector_analyzer_port`       | Implementado e ligado — `modules.selectors.selector_analyzer.SelectorAnalyzer` (ver ADR 0008), alimentado pelo Browser Data Collector para cada elemento real coletado (ADR 0013) |
| 8        | Screenshot Engine      | `screenshot_engine_port`       | Implementado e ligado — `modules.screenshots.screenshot_engine.ScreenshotEngine` (ver ADR 0009), alimentado com screenshots reais (`page.screenshot()`) pelo Browser Data Collector (ADR 0013) |
| 9        | Export Engine          | `export_engine_port`           | Implementado e ligado — `modules.export.export_engine.ExportEngine` (ver ADR 0010), chamado ao final de `StopCapture` (ADR 0012); a exportação real agora tem sucesso, pois o Browser Data Collector coleta os metadados de navegador exigidos (ADR 0013) |
| 10       | Log Engine             | `log_engine_port`              | Implementado e ligado — `infrastructure.logging.log_engine.LoguruLogEngine` (ver ADR 0011), instanciado por `bootstrap.create_controller` e injetado em todos os módulos |
| —        | Browser Data Collector | `browser_data_collector_port`  | Implementado e ligado — `infrastructure.browser.browser_data_collector.BrowserDataCollector` (ver ADR 0013); ponte entre o navegador real e Element Recorder/Selector Analyzer/Screenshot Engine, sem capítulo próprio no Module Specifications original |

## Checklist de desbloqueio na CLI (ADR 0003)

Cada módulo pendente acima destrava um pedaço específico da CLI
(`presentation/cli/`). Esta tabela existe para que, ao implementar um
módulo, a etapa **não termine sem também conectar o comando
correspondente** — hoje todos os 5 comandos "casca" chamam
`presentation.cli.handlers.pending.announce_pending(...)`, que deve ser
substituído pela chamada real assim que o módulo listado existir.

| Módulo (Capítulo) | Desbloqueia na CLI | Arquivo a alterar quando o módulo existir | Feito? |
| --- | --- | --- | --- |
| Browser Manager (3) | `snkb record`: abrir navegador + aguardar login manual | `bootstrap.create_controller` (wiring) | ☑ |
| Session Manager (4) | `snkb record`: sessão de fato criada/rastreada (evento `SessionStarted`) | `bootstrap.create_controller` | ☑ |
| Navigation Recorder (5) | `snkb record`: contador "Páginas" reflete navegação real (`PageChanged` do Browser Manager encaminhado para `observe_navigation()` + `capture_page()`) | `bootstrap.create_controller` / `ApplicationController._on_domain_event` | ☑ |
| Element Recorder (6) | `snkb record`: contador "Elementos" reflete elementos reais coletados pelo Browser Data Collector a cada página estável (ADR 0013) | `bootstrap.create_controller` + `infrastructure/browser/browser_data_collector.py` | ☑ |
| Selector Analyzer (7) | Seletores reais gerados por elemento coletado, disponíveis em `selectors.json` na exportação (ADR 0013) | `infrastructure/browser/browser_data_collector.py` | ☑ |
| Screenshot Engine (8) | `snkb record`: contador "Screenshots" reflete capturas reais (`page.screenshot()`) após login, navegações e antes do encerramento (ADR 0013) | `infrastructure/browser/browser_data_collector.py` + `InMemoryScreenshotStore` | ☑ |
| Export Engine (9) | `snkb record`: `ExportCompleted`/`ExportFailed` já tratados pela CLI — a exportação real agora **tem sucesso**, pois o Browser Data Collector coleta os metadados de navegador exigidos (ADR 0013); **`snkb validate`**/**`snkb open`** continuam pendentes (precisam descobrir a sessão mais recente em disco, não apenas ter o Export Engine ligado) | `presentation/cli/commands/validate.py`/`open_folder.py` + descoberta de sessão em disco | ☑ (Export Engine ligado e exportando com sucesso; comandos `validate`/`open` ainda não) |
| Log Engine (10) | Logging estruturado ativo durante `snkb record`; **`snkb logs`** continua pendente (mesma razão do item acima: precisa ler `logs/` de uma sessão específica, não só ter o Log Engine ligado) | `presentation/cli/commands/logs.py` + descoberta de sessão em disco | ☐ (Log Engine ligado; comando ainda não) |
| Configuration Manager (SAD, não numerado no Module Specifications) | **`snkb config`** passa a funcionar; recarregamento em tempo de execução e mensagens de erro por campo (CFG-006) | `infrastructure/configuration/` (novo); `presentation/cli/commands/config.py` | ☐ — `bootstrap.py` hoje só tem um carregador mínimo, não uma implementação de `ConfigurationProviderPort` (ver ADR 0012) |
| Application Controller (nenhum capítulo próprio — é o composition root) | Todos os comandos deixam de propagar `NotImplementedError` de `create_controller`; `RecordCommandHandler.handle_domain_event` é notificado via `ApplicationControllerPort.subscribe()` (decisão do ADR 0003, concluída no ADR 0012) | `bootstrap.py`; `application/services/application_controller.py` (novo); `application/services/application_controller_port.py` (novo método `subscribe`) | ☑ (ver ADR 0012) |
| Browser Data Collector (sem capítulo próprio — ponte de infraestrutura) | `snkb record`: fecha o pipeline ponta a ponta — elementos, seletores, screenshots e metadados de sessão reais, exportação com sucesso | `infrastructure/browser/browser_data_collector.py` (novo); `application/ports/browser_data_collector_port.py` (novo); `bootstrap.py` | ☑ (ver ADR 0013) |

Ao concluir a etapa de um módulo, marque a linha correspondente e
atualize a coluna "Status" da tabela principal acima.

**`snkb status`/`snkb validate`/`snkb open`/`snkb logs` continuam
chamando `announce_pending`** mesmo com todos os módulos de dados
implementados e ligados: esses comandos rodam em um processo *novo*,
sem acesso à memória do processo que gravou a sessão — precisam de um
mecanismo de descoberta em disco (ler `session.json`/`manifest.json`
da exportação mais recente), que é uma responsabilidade distinta,
ainda não implementada (ver ADR 0012, "Consequências").

Desde o ADR 0013, `snkb record` produz uma Base de Conhecimento real e
completa (elementos, seletores, screenshots e metadados de sessão
verdadeiros, exportação concluída com sucesso) — confirmado por testes
de integração com Chromium real e um teste de aceite com um app HTML
local de quatro páginas.
