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
| 3        | Browser Manager        | `browser_manager_port`         | Implementado — `infrastructure.browser.browser_manager.PlaywrightBrowserManager` (ver ADR 0004); ainda não conectado a `bootstrap.create_controller` |
| 4        | Session Manager        | `session_manager_port`         | Implementado — `modules.session.session_manager.SessionManager` (ver ADR 0005); ainda não conectado a `bootstrap.create_controller` |
| 5        | Navigation Recorder    | `navigation_recorder_port`     | Implementado — `modules.navigation.navigation_recorder.NavigationRecorder` (ver ADR 0006); ainda não conectado a `bootstrap.create_controller` |
| 6        | Element Recorder       | `element_recorder_port`        | Implementado — `modules.elements.element_recorder.ElementRecorder` (ver ADR 0007); ainda não conectado a `bootstrap.create_controller` |
| 7        | Selector Analyzer      | `selector_analyzer_port`       | Implementado — `modules.selectors.selector_analyzer.SelectorAnalyzer` (ver ADR 0008); ainda não conectado a `bootstrap.create_controller` |
| 8        | Screenshot Engine      | `screenshot_engine_port`       | Implementado — `modules.screenshots.screenshot_engine.ScreenshotEngine` (ver ADR 0009); ainda não conectado a `bootstrap.create_controller` |
| 9        | Export Engine          | `export_engine_port`           | Implementado — `modules.export.export_engine.ExportEngine` (ver ADR 0010); ainda não conectado a `bootstrap.create_controller` |
| 10       | Log Engine             | `log_engine_port`              | Pendente      |

## Checklist de desbloqueio na CLI (ADR 0003)

Cada módulo pendente acima destrava um pedaço específico da CLI
(`presentation/cli/`). Esta tabela existe para que, ao implementar um
módulo, a etapa **não termine sem também conectar o comando
correspondente** — hoje todos os 5 comandos "casca" chamam
`presentation.cli.handlers.pending.announce_pending(...)`, que deve ser
substituído pela chamada real assim que o módulo listado existir.

| Módulo (Capítulo) | Desbloqueia na CLI | Arquivo a alterar quando o módulo existir | Feito? |
| --- | --- | --- | --- |
| Browser Manager (3) | `snkb record`: abrir navegador + aguardar login manual (hoje ainda para no `NotImplementedError` de `create_controller`, pois falta o Application Controller para instanciar o `PlaywrightBrowserManager`) | `bootstrap.create_controller` (wiring), sem mudança em `record_handler.py` | ☑ adapter pronto (ADR 0004) / ☐ ligado ao bootstrap |
| Session Manager (4) | `snkb record`: sessão de fato criada/rastreada (evento `SessionStarted`); **`snkb status`** passa a funcionar | `bootstrap.create_controller`; `presentation/cli/commands/status.py` (remover `announce_pending`, implementar consulta real via `GetSessionStatus`/`GetSessionStatistics`) | ☑ adapter pronto (ADR 0005) / ☐ ligado ao bootstrap |
| Navigation Recorder (5) | `snkb record`: contador "Páginas" deixa de ficar sempre associado só ao evento `PageCaptured` já simulável — passa a refletir navegação real | `bootstrap.create_controller` (wiring: encaminhar `PageChanged`/`UrlChanged` do Browser Manager para `observe_navigation()` + `capture_page()`) | ☑ adapter pronto (ADR 0006) / ☐ ligado ao bootstrap |
| Element Recorder (6) | `snkb record`: contador "Elementos" (hoje fixo em 0 — ver `RecordingCounters`/`RecordingCounterAggregator`) | `presentation/cli/status_aggregator.py` (adicionar caso para `ElementsCaptured`); `bootstrap.create_controller` (wiring: encaminhar DOM observado para `observe_elements()` + `capture_elements()`) | ☑ adapter pronto (ADR 0007) / ☐ ligado ao bootstrap |
| Selector Analyzer (7) | Nenhum comando CLI direto — alimenta `selectors.json`, consumido pelo Export Engine | `bootstrap.create_controller` (wiring: `register_session_for_page()` + chamar `analyze()` após cada `ElementsCaptured`) | ☑ adapter pronto (ADR 0008) / ☐ ligado ao bootstrap |
| Screenshot Engine (8) | `snkb record`: contador "Screenshots" (hoje fixo em 0) | `presentation/cli/status_aggregator.py` (adicionar caso para `ScreenshotCreated`); `bootstrap.create_controller` (wiring: encaminhar capturas do Playwright para `stage_capture()` + `capture_page()`/`capture_modal()`/`capture_popup()`) | ☑ adapter pronto (ADR 0009) / ☐ ligado ao bootstrap |
| Export Engine (9) | `snkb record`: exportação final e caminho da Base de Conhecimento (`ExportCompleted`/`ExportFailed` já tratados); **`snkb validate`** e **`snkb open`** passam a funcionar | `presentation/cli/commands/validate.py` e `open_folder.py` (remover `announce_pending`); `bootstrap.create_controller` (wiring: injetar os 5 módulos + `output_directory` de `AppConfig`) | ☑ adapter pronto (ADR 0010) / ☐ ligado ao bootstrap |
| Log Engine (10) | **`snkb logs`** passa a funcionar; contador "Logs" em `snkb record` | `presentation/cli/commands/logs.py` (remover `announce_pending`) | ☐ |
| Configuration Manager (SAD, não numerado no Module Specifications) | **`snkb config`** passa a funcionar; `snkb record --instance-url` passa a ter valor padrão vindo de `config/default.json` | `presentation/cli/commands/config.py`; `presentation/cli/commands/record.py` | ☐ |
| Application Controller (nenhum capítulo próprio — é o composition root) | Todos os comandos deixam de propagar `NotImplementedError` de `create_controller`; decide como eventos chegam a `RecordCommandHandler.handle_domain_event` (callback direto vs. Protocol de assinatura — decisão adiada no ADR 0003) | `bootstrap.py` (implementação real de `create_controller`) | ☐ |

Ao concluir a etapa de um módulo, marque a linha correspondente e
atualize a coluna "Status" da tabela principal acima.
