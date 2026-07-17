# ADR 0010 — Implementação do Export Engine

## Status

Aceito — 2026-07-17.

## Contexto

Sétimo e último módulo "recorder/analyzer" do projeto antes do Log
Engine e do Application Controller (Module Specifications, Capítulo
9; AI Development Guide, etapa 10), depois do Browser Manager (ADR
0004), Session Manager (ADR 0005), Navigation Recorder (ADR 0006),
Element Recorder (ADR 0007), Selector Analyzer (ADR 0008) e Screenshot
Engine (ADR 0009). O próprio Port já resolve a dúvida arquitetural
central deste módulo: "Consolidates data produced by every other
module into the on-disk Knowledge Base. Never captures data itself"
(9.4). Diferente de todos os módulos anteriores — que eram
deliberadamente síncronos e livres de I/O —, este é o primeiro que
**realmente grava arquivos em disco**: é o próprio propósito do
módulo, não uma violação da arquitetura. Usa somente a biblioteca
padrão (`pathlib`, `hashlib`, `html`, serialização JSON via Pydantic)
— nunca Playwright, então continua fora de `infrastructure/`.

## Decisão

### Depende dos cinco módulos de dados, não faz observação própria

Ao contrário de todos os módulos anteriores (que precisavam de
`observe_*`/`stage_*` para receber dados brutos de fora), o Export
Engine não tem NENHUM método de intake — ele lê diretamente do que já
está em memória em `SessionManagerPort`, `NavigationRecorderPort`,
`ElementRecorderPort`, `SelectorAnalyzerPort` e `ScreenshotEnginePort`
(exatamente a lista declarada em `modules/export/__init__.py`, 9.5).
Isso simplifica bastante o construtor comparado aos módulos anteriores
— não há estado de "observação pendente" para gerenciar.

### `get_screenshots(page_id)` adicionado ao Screenshot Engine (ADR 0009)

`ScreenshotEnginePort` só expõe `get_screenshot(screenshot_id)` (um por
vez). Para montar `screenshots/<page_id>.json` e a lista de
`screenshot_id`s em `pages/<page_id>.json`, o Export Engine precisa
listar todas as capturas de uma página — então
`ScreenshotEngine.get_screenshots(page_id) -> list[Screenshot]` foi
adicionado como método extra (além do Port), mesmo padrão de
`ElementRecorder.get_frames()` (ADR 0007). Mudança aditiva, de baixo
risco, num módulo já implementado.

### `output_directory` vem de fora, `file_name`/estrutura de diretório são deste módulo

O construtor recebe `output_directory: Path` diretamente (não o
`AppConfig` inteiro, mesmo padrão do Browser Manager receber só o que
precisa). Cada sessão ganha um diretório exclusivo
`output_directory/<session_id>/` (RN-005), com a estrutura:
`session.json`, `navigation.json`, `selectors.json`,
`statistics.json`, `manifest.json`, `report.html`, `pages/<page_id>.
json`, `screenshots/<page_id>.json` (metadados) e, quando disponível,
`screenshots/<file_name>.png` (bytes reais).

### Metadados de sessão incompletos bloqueiam a exportação, não são preenchidos com placeholder

`SessionJsonModel` exige `recording_start`, `browser`,
`browser_version`, `operating_system`, `screen_resolution` e
`viewport` — todos opcionais na entidade `Session` hoje, porque nada
ainda popula esses campos via `SessionManager.update_metadata()` (ver
"Consequências" do ADR 0005). Em vez de inventar valores como
`"unknown"` ou `0x0` (que pareceriam dados reais num arquivo
persistido), `export_session()` levanta `ExportValidationError`
listando os campos ausentes. Isso é o comportamento honesto e correto
hoje: a exportação de uma sessão recém-criada, sem que o Application
Controller ainda colete metadados do navegador, **deve falhar**, não
produzir um `session.json` enganoso.

### Sem bytes de screenshot em lugar nenhum do sistema ainda

Nenhum módulo hoje guarda os bytes reais de uma captura de tela — a
entidade `Screenshot` só tem metadados (ADR 0009). Por isso
`export_pages()` sempre grava o manifesto `screenshots/<page_id>.json`
(metadados), mas só grava o arquivo `.png` de fato se um
`screenshot_bytes_provider: Callable[[UUID], bytes | None]` for
injetado no construtor (opcional, `None` por padrão). Sem ele, a
exportação continua funcionando (não falha), só sem as imagens —
limitação declarada, não escondida, à espera do dia em que o
Application Controller conseguir manter esses bytes acessíveis entre a
captura (Playwright, assíncrono) e a exportação (síncrona).

### Escrita atômica via arquivo temporário + rename

Todo escrita (`_write_json_model`, o relatório HTML, os bytes de
screenshot) segue o padrão "escreve em `<arquivo>.tmp`, depois
`Path.replace()`" — evita que uma falha no meio da escrita deixe um
arquivo corrompido no lugar do arquivo final. `clear_temp()` limpa
qualquer `.tmp` esquecido de uma exportação anterior interrompida;
`export_manifest()` ignora arquivos `.tmp` ao montar o inventário.

### `export_manifest()` sempre roda por último, computando hashes reais

Como o manifesto precisa do SHA-256 de cada arquivo já gravado, ele só
faz sentido depois que os demais passos escreveram seus arquivos.
`export()` (o método "faça tudo") chama os passos nessa ordem: sessão,
navegação, páginas, seletores, estatísticas, relatório, manifesto —
publicando `ExportProgress` a cada etapa. Qualquer exceção nesse meio
publica `ExportFailed(reason)` e relança a exceção original (o
chamador sempre sabe que falhou e por quê).

### `validate()` faz validação de schema E de integridade de checksum

Reconstrói cada modelo Pydantic a partir do arquivo gravado
(round-trip real, não confiança cega) e, para cada entrada do
manifesto, recomputa o SHA-256 do arquivo no disco e compara com o
valor registrado — detecta tanto arquivo ausente quanto arquivo
adulterado depois da exportação. Retorna `bool` (nunca lança), como o
Port exige; qualquer `OSError`/`ValueError` (inclusive
`pydantic.ValidationError`, que herda de `ValueError`) durante a
leitura é tratado como "inválido", registrado via `LogEnginePort.
warning()`.

### Sem novas exceções

Diferente de todos os módulos anteriores, nenhuma exceção nova foi
necessária — `ExportValidationError` (já existente) cobre tanto
metadados de sessão incompletos quanto descompasso de sessão entre o
Navigation Recorder e o `session_id` solicitado.

## Testes

`tests/unit/modules/export/test_export_engine.py`: usa o fixture
`tmp_path` do pytest como `output_directory` (nunca toca o sistema de
arquivos real do projeto). Cobre: metadados de sessão incompletos,
descompasso de sessão em `export_navigation()`, geração de
`pages/<id>.json` com elementos e seletores embutidos, manifesto de
screenshots (presente/ausente conforme haja capturas), escrita real de
bytes PNG quando um `screenshot_bytes_provider` é passado, divisão
`best_strategy`/`fallback_strategies` em `selectors.json`, agregação de
`statistics.json`, checksums do manifesto (incluindo exclusão de
arquivos `.tmp`), escape de HTML no relatório (título malicioso com
`<script>`), pipeline completo de `export()` seguido de `validate() ==
True`, propagação de `ExportFailed` em caso de erro, detecção de
arquivo adulterado por `validate()`, e `clear_temp()` isolado.

## Consequências

- `snkb validate`/`snkb open` ainda não funcionam ponta a ponta — falta
  o Application Controller instanciar `ExportEngine` com os cinco
  módulos de dados e o `output_directory` de `AppConfig` (ver
  checklist em `docs/module-specs/README.md`).
- Nenhum arquivo `.png` real será gravado até que exista um mecanismo
  concreto de manter bytes de screenshot acessíveis entre a captura e
  a exportação — hoje só o manifesto de metadados é gravado.
- `total_events`/`total_logs` em `statistics.json` ficam fixos em `0`
  até o Log Engine (Capítulo 10) existir — não fabricados.
- Log Engine (próximo módulo, mas implementado em
  `infrastructure/logging/`, não em `modules/`, já que grava arquivos
  de log reais) poderá alimentar `total_logs` sem nenhuma mudança
  neste módulo.
