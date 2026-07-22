# ADR 0014 — Session Discovery, Folder Opener e Log Reader

## Status

Aceito — 2026-07-21.

## Contexto

Desde o ADR 0013, `snkb record` produz uma Base de Conhecimento real e
completa. `snkb status`, `validate`, `open` e `logs`, no entanto,
continuavam chamando `announce_pending` — não por módulos ausentes
(todos os oito módulos centrais + Application Controller + Browser
Data Collector já existem), mas pelo motivo registrado nas
"Consequências" do ADR 0012: cada invocação de `snkb <comando>` é um
**processo novo**. `SessionManager`/`NavigationRecorder`/etc. guardam
estado só em memória, que não sobrevive ao fim do processo que gravou
a sessão. Descobrir "a sessão mais recente" a partir de um processo
diferente exige ler os artefatos já exportados em disco
(`session.json`/`statistics.json`), um mecanismo de leitura pós-
exportação que nenhum ADR anterior implementava.

Além da descoberta em si, `open` precisa abrir um diretório no
explorador de arquivos do sistema operacional (chamada de
infraestrutura, nunca permitida em `application/`, ARQ-001) e `logs`
precisa ler de volta os arquivos JSON Lines que o Log Engine já grava
(ADR 0011) — duas responsabilidades distintas, mas pequenas o
suficiente para caber neste mesmo ADR.

## Decisão

### Três Ports novos, cada um com uma única responsabilidade

`application/ports/session_discovery_port.py`:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class SessionSummary:
    session_id: UUID
    status: str
    instance_url: str
    export_directory: Path
    recording_start: datetime
    recording_end: datetime | None
    total_pages: int
    total_elements: int
    total_screenshots: int
    error_count: int

class SessionDiscoveryPort(Protocol):
    def list_recent(self, limit: int = 20) -> list[SessionSummary]: ...
    def find(self, session_id: UUID) -> SessionSummary | None: ...
```

`SessionSummary` nunca duplica o conteúdo completo de `session.json` —
só o que os comandos `status`/`validate`/`open`/`logs` precisam para
identificar e descrever uma sessão, mesmo princípio já seguido por
`PageCaptureResult` (ADR 0013).

`application/ports/folder_opener_port.py`: `FolderOpenerPort.open(path:
Path) -> None`, para que `application/` nunca precise importar
`os.startfile`/`subprocess` diretamente.

`application/ports/log_reader_port.py`: `LogReaderPort.
read_session_logs(session_id, limit) -> list[LogRecordSummary]`,
distinto de `LogEnginePort` — aquele só expõe o registro em memória do
processo *atual* (`export()`/`statistics()`); este lê os arquivos já
persistidos por execuções anteriores.

### Implementações concretas em `infrastructure/`

- `infrastructure/storage/session_discovery.py`: `DiskSessionDiscovery`
  varre `output_directory/*/session.json`, valida cada um via
  `SessionJsonModel.model_validate_json` e tenta ler o
  `statistics.json` irmão (zeros se ausente/malformado — sessão ainda
  não totalmente exportada), ordena por `recording_start` decrescente.
  Um diretório de sessão malformado é ignorado (aviso via
  `LogEnginePort`) em vez de derrubar a listagem inteira — mesmo
  princípio de tolerância a falha parcial já usado pelo Browser Data
  Collector (ADR 0013).
- `infrastructure/storage/folder_opener.py`: `OsFolderOpener` usa
  `os.startfile` no Windows (plataforma alvo do projeto — ver o
  tratamento de UTF-8 do console em `presentation/cli/main.py`), com
  fallback `subprocess.run(["open"/"xdg-open", ...])` em outros SOs
  só para não quebrar a suíte de testes fora do Windows — nunca
  validado como fluxo principal do produto.
- `infrastructure/logging/log_reader.py`: `DiskLogReader` lê
  `logs/snkb_*.log` (JSON Lines, `serialize=True`, já gravado pelo
  `LoguruLogEngine`, ADR 0011), filtra por
  `record.extra.session_id == str(session_id)` — o mesmo `session_id`
  que cada módulo já passa como contexto
  (`log_engine.info(..., session_id=str(session_id))` →
  `logger.bind(**context)` → `record.extra`), sem exigir nenhuma
  mudança nos módulos que já logam.

### `ApplicationController`: três parâmetros novos, obrigatórios

Diferente de `browser_manager_factory`/`browser_data_collector_factory`
(opcionais só para compatibilidade retroativa durante a migração do
ADR 0013), `session_discovery`, `folder_opener` e `log_reader` são
parâmetros **obrigatórios** do construtor — não há motivo de
compatibilidade retroativa para eles, e um `ApplicationController`
sem essas três peças não consegue atender `status`/`validate`/`open`/
`logs`.

`dispatch()` ganha `case OpenExportFolder(session_id=session_id)` (o
comando já existia em `application/commands/commands.py`, não
utilizado até aqui): resolve o `SessionSummary` via
`session_discovery.find(session_id)`; se `None`, publica
`ErrorOccurred` (mesmo padrão já usado em `_handle_start_capture`) em
vez de levantar uma exceção — consistente com o resto do
`ApplicationController`, que sempre publica eventos para falhas
esperadas de tempo de execução.

`query()` ganha três casos: `GetRecentSessions(limit)` →
`session_discovery.list_recent(limit)` (finalmente implementado — o
ADR 0012 já reservava esta consulta, levantando `NotImplementedError`
explicitamente até este ADR); `ValidateExport(session_id)` →
`export_engine.validate(session_id)` (o Export Engine, desde o ADR
0010, já é inteiramente baseado em disco — só faltava saber *qual*
`session_id` consultar); `GetSessionLogs(session_id, limit)` →
`log_reader.read_session_logs(...)`.

### Os 4 comandos da CLI: descobrir, então agir

`status`/`validate`/`open`/`logs` seguem todos o mesmo padrão de duas
consultas: `query(GetRecentSessions(limit=1))` para descobrir a sessão
mais recente (lista vazia → mensagem clara, saída 1, nunca um
traceback), depois a ação específica do comando
(`ValidateExport`/`OpenExportFolder`/`GetSessionLogs`, ou nenhuma
consulta extra para `status`, que já tem tudo em `SessionSummary`).

`status.py` para de usar `RecordingCounters`/`RecordingState`
(`presentation/cli/view_models.py`) — esses são orientados a evento,
específicos do laço ao vivo de `snkb record`; uma leitura pontual de
disco tem um formato de dados diferente (`SessionSummary`), então
ganha seu próprio formatter,
`presentation/cli/formatters/session_summary_formatter.py`, em vez de
forçar o formato antigo.

`presentation/cli/handlers/pending.py` (`announce_pending`/
`require_module`) foi removido: nenhum comando o chama mais depois
deste ADR e do ADR 0015 (só `config` ainda dependia dele).

## Testes

`tests/unit/infrastructure/storage/test_session_discovery.py`:
diretório de saída ausente, sessão válida com/sem `statistics.json`,
ordenação por `recording_start`, `limit`, diretório malformado
ignorado (com aviso) sem derrubar os demais, `find()` com sessão
existente/inexistente.

`tests/unit/infrastructure/storage/test_folder_opener.py`: um cenário
por plataforma (`win32`/`darwin`/linux), sempre com `os.startfile`/
`subprocess.run` substituídos por duplos — nunca abre uma janela real
do explorador de arquivos durante a suíte.

`tests/unit/infrastructure/logging/test_log_reader.py`: usa o
`LoguruLogEngine` real (não um formato JSON escrito à mão) para
gravar os arquivos e depois lê de volta — filtragem por sessão,
ordenação mais recente primeiro, `limit`, registros sem `session_id`
ignorados, linha malformada ignorada.

`tests/unit/application/services/test_application_controller.py`:
estendido com duplos de `SessionDiscoveryPort`/`FolderOpenerPort`/
`LogReaderPort` na harness; novos testes para os três casos de
`query()` e para `dispatch(OpenExportFolder)` (sessão encontrada e
sessão inexistente → `ErrorOccurred`).

`tests/unit/presentation/cli/test_disk_backed_commands.py`: os 4
comandos via `CliRunner`, cobrindo "nenhuma sessão encontrada" e o
caminho feliz de cada um — `open` sempre com `os.startfile`
substituído por um duplo.

`tests/contract/test_ports.py`: os três Ports novos expõem exatamente
os métodos definidos.

`tests/integration/test_application_controller_integration.py`:
estendido para, depois de uma exportação real com Chromium, consultar
`GetRecentSessions`/`ValidateExport` e despachar `OpenExportFolder`
contra o `DiskSessionDiscovery`/`DiskLogReader` reais (só o
`FolderOpenerPort` continua sendo um duplo, para não abrir uma janela
real durante a suíte).

`tests/acceptance/test_local_recording_flow.py`: estendido para, após
a gravação de 4 páginas com Chromium real, invocar `status`/
`validate`/`open`/`logs`/`config` via `CliRunner` como processos
separados (a mesma garantia que a produção depende) contra a sessão
recém-exportada.

## Consequências

- **`snkb status`/`validate`/`open`/`logs` funcionam de ponta a
  ponta**: descobrem a sessão mais recente em disco e executam sua
  ação sem depender de nenhum estado em memória do processo que
  gravou a sessão.
- `GetRecentSessions` deixa de levantar `NotImplementedError` — a
  lacuna documentada desde o ADR 0012 está fechada.
- `presentation/cli/handlers/pending.py` foi removido — não há mais
  nenhum comando "casca" no projeto (ver ADR 0015 para `config`, o
  último).
- `OsFolderOpener` no Linux/macOS nunca foi exercitado manualmente
  contra um explorador de arquivos real — só o caminho Windows
  (`os.startfile`) é o alvo de produção deste projeto.
