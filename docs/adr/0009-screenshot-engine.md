# ADR 0009 — Implementação do Screenshot Engine

## Status

Aceito — 2026-07-17.

## Contexto

Sexto módulo central do projeto (Module Specifications, Capítulo 8;
AI Development Guide, etapa 9), depois do Browser Manager (ADR 0004),
Session Manager (ADR 0005), Navigation Recorder (ADR 0006), Element
Recorder (ADR 0007) e Selector Analyzer (ADR 0008). A própria entidade
`Screenshot` (`domain.entities.screenshot`) já resolve a dúvida
arquitetural mais importante deste módulo, na própria docstring: "o
conteúdo binário em si é gravado em disco exclusivamente pelo Export
Engine". Ou seja, o Screenshot Engine nunca grava um arquivo PNG,
nunca chama `page.screenshot()`, nunca importa Playwright — cataloga
apenas metadados (dimensões, tipo de captura, nome de arquivo,
timestamp) de capturas já realizadas por quem tem acesso ao navegador.
Isso é consistente com o padrão síncrono/sem I/O de todos os módulos
`modules/*` implementados até aqui (`ScreenshotEnginePort` também não
tem nenhum método `async`).

## Decisão

### `stage_capture()` recebe só dimensões, nunca bytes

Novo método `stage_capture(session_id, page_id, capture_type,
observation: RawScreenshotObservation)`, além da superfície mínima do
Port (mesmo padrão dos ADRs 0006/0007/0008).
`RawScreenshotObservation` carrega apenas `width`, `height` e um
`byte_size` opcional (para uma validação estrutural mínima — "o
arquivo não está vazio" — sem nunca precisar do conteúdo em si).
`capture()`/`capture_page()`/`capture_modal()`/`capture_popup()`
consomem essa observação pendente para construir a entidade
`Screenshot`.

### `file_name` é gerado por este módulo, não recebido de fora

Diferente do Navigation Recorder (que recebe a URL pronta) e do
Element Recorder (que recebe atributos de DOM prontos), o nome do
arquivo é uma decisão de convenção puramente local — não depende de
nenhum dado que só o navegador conhece. `capture()` gera
deterministicamente `f"{page_id}_{capture_type.value}_{sequência:03d}.png"`,
com um contador por página que nunca reinicia durante a vida do
processo (garante nomes únicos mesmo com múltiplas capturas do mesmo
tipo na mesma página).

### Conexão real com `CapturePolicyModel`

Diferente do Element Recorder (onde `capture_field_values`/
`mask_sensitive_fields` não tinham nenhum campo correspondente na
entidade `Element` para afetar, ADR 0007), aqui a conexão é direta e
observável:

- `capture_policy.capture_screenshots` (padrão `True`): se `False`,
  `capture()` nunca produz uma captura — publica `ScreenshotSkipped` e
  levanta `NoPendingCaptureError` (o Port exige retornar um
  `Screenshot`, então não é possível "retornar vazio"; o chamador deve
  verificar a política antes ou tratar a exceção).
- `capture_policy.full_page_screenshots` (padrão `False`): decide se
  `capture_page()` usa `ScreenshotType.FULL_PAGE` ou
  `ScreenshotType.VIEWPORT`.

### `capture_page`/`capture_modal`/`capture_popup` são atalhos de `capture()`

Mapeamento direto e óbvio para os tipos do enum `ScreenshotType`:
`capture_page` → `FULL_PAGE`/`VIEWPORT` (conforme a política acima),
`capture_modal` → `MODAL`, `capture_popup` → `POPUP`. Os tipos
`ELEMENT` e `REGION` do enum não têm um atalho próprio no Port —
continuam acessíveis via `capture(page_id, ScreenshotType.ELEMENT)`
diretamente, quando um futuro chamador precisar deles.

### `validate()` é puramente estrutural

Sem acesso ao arquivo real (que nem existe neste módulo), a validação
verifica apenas o que já é conhecido: dimensões positivas e
`byte_size` (se informado) maior que zero. Não confirma que a imagem é
um PNG válido nem que o conteúdo visual está correto — isso exigiria
abrir o arquivo, responsabilidade do Export Engine (que efetivamente
grava e poderá, naquele momento, fazer uma validação mais profunda).

### `ScreenshotUpdated` não é usado por nenhum método deste módulo

O Port não tem nenhum método `update`; o evento existe em
`screenshot_events.py` mas nenhuma operação atual o dispara — fica
disponível para um cenário futuro (ex.: um `RelabelArtifact` que
também reassocie um screenshot). Mesma situação de `ElementCaptureError`
não usado pelo Element Recorder (ADR 0007): documentado, não
escondido.

### Duas novas exceções em `screenshot_exceptions.py`

- `NoPendingCaptureError` — `capture()` chamado sem `stage_capture()`
  prévio, ou com a política desabilitando screenshots.
- `ScreenshotNotFoundError` — `delete()` referencia um `screenshot_id`
  nunca capturado.

`ScreenshotCaptureError` (já existente) é reaproveitado para
dimensões inválidas — ainda dentro do seu escopo documentado ("captura
produz um arquivo corrompido"). `InsufficientDiskSpaceError` não é
usado por este módulo (não grava nada em disco); pertence ao Export
Engine.

## Testes

`tests/unit/modules/screenshots/test_screenshot_engine.py`: captura
sem staging, política desabilitando screenshots (exceção +
`ScreenshotSkipped`), construção e publicação de `ScreenshotCreated`,
dimensões inválidas (`ScreenshotCaptureError` + `ScreenshotFailed`),
numeração sequencial de arquivo entre capturas, os três atalhos
(`capture_page` com e sem `full_page_screenshots`, `capture_modal`,
`capture_popup`), `validate()` (válido, `byte_size` zero, id
desconhecido), `get_screenshot()`, `delete()` (com e sem sucesso),
`clear()` isolado por página (inclusive descartando observações
pendentes ainda não capturadas) e `statistics()`.

## Consequências

- `snkb record`: o contador "Screenshots" ainda não reflete captura
  real — falta o Application Controller chamar `page.screenshot()`
  (assíncrono, via Browser Manager) e encaminhar as dimensões
  resultantes para `stage_capture()` (ver checklist em
  `docs/module-specs/README.md`).
- Export Engine (Capítulo 9, próximo módulo) será o primeiro a de fato
  gravar bytes de imagem em disco — usará `get_screenshot()`/
  `validate()` para montar o manifesto e decidir o que persistir.
- Os tipos `ELEMENT`/`REGION` de `ScreenshotType` ficam sem atalho
  dedicado no Port; se o Application Controller precisar deles com
  frequência, um `capture_element(element_id)` poderia ser adicionado
  como método extra deste módulo no futuro, sem quebrar nada existente.
