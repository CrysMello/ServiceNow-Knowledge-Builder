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
| 3        | Browser Manager        | `browser_manager_port`         | Pendente      |
| 4        | Session Manager        | `session_manager_port`         | Pendente      |
| 5        | Navigation Recorder    | `navigation_recorder_port`     | Pendente      |
| 6        | Element Recorder       | `element_recorder_port`        | Pendente      |
| 7        | Selector Analyzer      | `selector_analyzer_port`       | Pendente      |
| 8        | Screenshot Engine      | `screenshot_engine_port`       | Pendente      |
| 9        | Export Engine          | `export_engine_port`           | Pendente      |
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
| Browser Manager (3) | `snkb record`: abrir navegador + aguardar login manual (hoje só dispara `StartCapture` e para no `NotImplementedError` de `create_controller`) | `bootstrap.create_controller` (wiring), sem mudança em `record_handler.py` | ☐ |
| Session Manager (4) | `snkb record`: sessão de fato criada/rastreada (evento `SessionStarted`); **`snkb status`** passa a funcionar | `bootstrap.create_controller`; `presentation/cli/commands/status.py` (remover `announce_pending`, implementar consulta real via `GetSessionStatus`/`GetSessionStatistics`) | ☐ |
| Navigation Recorder (5) | `snkb record`: contador "Páginas" deixa de ficar sempre associado só ao evento `PageCaptured` já simulável — passa a refletir navegação real | `bootstrap.create_controller` (wiring) | ☐ |
| Element Recorder (6) | `snkb record`: contador "Elementos" (hoje fixo em 0 — ver `RecordingCounters`/`RecordingCounterAggregator`) | `presentation/cli/status_aggregator.py` (adicionar caso para o evento de elemento capturado) | ☐ |
| Selector Analyzer (7) | Nenhum comando CLI direto — alimenta `selectors.json`, consumido pelo Export Engine | — | ☐ |
| Screenshot Engine (8) | `snkb record`: contador "Screenshots" (hoje fixo em 0) | `presentation/cli/status_aggregator.py` (adicionar caso para `ScreenshotCreated`) | ☐ |
| Export Engine (9) | `snkb record`: exportação final e caminho da Base de Conhecimento (`ExportCompleted`/`ExportFailed` já tratados); **`snkb validate`** e **`snkb open`** passam a funcionar | `presentation/cli/commands/validate.py` e `open_folder.py` (remover `announce_pending`) | ☐ |
| Log Engine (10) | **`snkb logs`** passa a funcionar; contador "Logs" em `snkb record` | `presentation/cli/commands/logs.py` (remover `announce_pending`) | ☐ |
| Configuration Manager (SAD, não numerado no Module Specifications) | **`snkb config`** passa a funcionar; `snkb record --instance-url` passa a ter valor padrão vindo de `config/default.json` | `presentation/cli/commands/config.py`; `presentation/cli/commands/record.py` | ☐ |
| Application Controller (nenhum capítulo próprio — é o composition root) | Todos os comandos deixam de propagar `NotImplementedError` de `create_controller`; decide como eventos chegam a `RecordCommandHandler.handle_domain_event` (callback direto vs. Protocol de assinatura — decisão adiada no ADR 0003) | `bootstrap.py` (implementação real de `create_controller`) | ☐ |

Ao concluir a etapa de um módulo, marque a linha correspondente e
atualize a coluna "Status" da tabela principal acima.
