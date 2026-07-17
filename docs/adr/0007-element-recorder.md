# ADR 0007 — Implementação do Element Recorder

## Status

Aceito — 2026-07-17.

## Contexto

Quarto módulo central do projeto (Module Specifications, Capítulo 6;
AI Development Guide, etapa 7), depois do Browser Manager (ADR 0004),
Session Manager (ADR 0005) e Navigation Recorder (ADR 0006).
`ElementRecorderPort` "identifica, classifica e cataloga elementos
encontrados em uma página" — mas, como os dois módulos anteriores,
todos os seus métodos são síncronos. Pelo mesmo raciocínio já aplicado
duas vezes (ADR 0005, ADR 0006): este módulo não pode inspecionar o
DOM real (isso exigiria chamadas assíncronas do Playwright), então ele
recebe atributos de DOM **já lidos** por quem tem acesso ao navegador
(hoje o futuro Application Controller), nunca os lê sozinho.

Ponto de atenção de segurança (RS-002, RS-011, RF-011): a entidade
`Element` (`domain.entities.element`) **não tem nenhum campo para o
valor de um campo de formulário** — apenas metadados estruturais
(tag, papel ARIA, rótulo, classes, etc.) e uma
`sensitivity_classification`. Ou seja, mesmo que o chamador tivesse
acesso ao valor real digitado pelo usuário, não haveria onde
armazená-lo nesta camada — a arquitetura já impede isso por
construção, e o Element Recorder não precisa (nem pode) implementar
nenhuma lógica de mascaramento de valor.

## Decisão

### `observe_elements()` recebe atributos brutos, nunca valores

Novo método `observe_elements(session_id, page_id, elements:
list[RawElementObservation])`, além da superfície mínima do Port
(mesmo padrão dos ADRs 0005/0006). `RawElementObservation` é um
dataclass simples com os atributos de DOM que o chamador já leu (tag,
role, type do input, accessible name, label, placeholder, id, name,
classes, required/readonly/disabled/visible/enabled) — nunca um campo
de valor. `capture_elements(page_id)` (a única forma exposta pelo Port
de efetivamente processar o lote) consome a observação pendente daquela
página.

### Classificação semântica é responsabilidade real deste módulo

Diferente do Navigation Recorder (que não classifica nada, só
reencaminha URLs), aqui "classifica" é literal no nome do Port. A
heurística (`_classify`) usa apenas semântica HTML/ARIA padrão e bem
estabelecida — não inventa nenhuma convenção específica do ServiceNow
que eu não pudesse confirmar:

1. Se um `role` ARIA reconhecido está presente, ele tem prioridade
   (ex.: `role="grid"` → `GRID`, mesmo em uma `<div>`).
2. Para `<input>`, o atributo `type` mapeia para `PASSWORD`, `EMAIL`,
   `PHONE`, `NUMBER`, `DATE`, `DATETIME`, `CHECKBOX`, `RADIO_BUTTON` ou
   `TEXTBOX` (padrão).
3. Para outras tags, um mapa direto (`textarea`, `select`, `button`,
   `a`, `table`, `form`).
4. Caso contrário, `UNKNOWN`.

Tipos específicos do ServiceNow (`FORM_LAYOUT`, `WORKSPACE_COMPONENT`,
`UI_BUILDER_COMPONENT`, `SERVICE_PORTAL_WIDGET`,
`NOW_EXPERIENCE_COMPONENT`, `RELATED_LIST`) não têm heurística própria
— exigiriam conhecimento real das classes CSS/estrutura interna do
ServiceNow que não está disponível para verificação nesta etapa. Um
campo opcional `semantic_type_hint` em `RawElementObservation` permite
que o chamador (que pode ter esse conhecimento específico) informe a
classificação correta diretamente, sobrepondo a heurística genérica.

### Classificação de sensibilidade é conservadora por padrão

`sensitivity_classification` é `SENSITIVE` quando o tipo semântico é
`PASSWORD` ou quando o chamador passa `is_sensitive_hint=True`
(sinalizando, por exemplo, um campo de CPF/SSN reconhecido por nome ou
rótulo). Caso contrário, `NONE`. Os valores `MASKED`/`OMITTED` do enum
`SensitivityClassification` não são produzidos por este módulo: como
não existe nenhum campo de valor na entidade `Element` para mascarar
ou omitir, atribuir esses estados aqui seria fabricar um
comportamento que não existe. `CapturePolicyModel.capture_field_values`/
`mask_sensitive_fields` (`AppConfig`) não foram conectados a este
módulo pelo mesmo motivo — não haveria nenhum efeito observável na
entidade `Element` (ver "Consequências").

### Fingerprint e deduplicação, como no Navigation Recorder

Cada elemento recebe um `fingerprint` (hash SHA-256 de
`frame_id + tag + html_id + name + role + accessible_name + label`).
Uma nova chamada a `observe_elements()`/`capture_elements()` para a
mesma página reaproveita o `Element` existente quando o fingerprint
já é conhecido (atualiza atributos como `disabled`/`visible` em vez de
criar um duplicado), replicando exatamente a estratégia de
deduplicação por fingerprint do Navigation Recorder (ADR 0006).

### Frames são gerenciados internamente, sem hierarquia de pai

RF-009 exige associar elementos a frames. Cada `RawElementObservation`
carrega `frame_origin`/`frame_selector`; o Element Recorder deduplica
frames por `(origin, selector)` dentro de cada página e atribui um
`FrameId` estável. `Frame.parent_frame_id` fica sempre `None` nesta
etapa — resolver hierarquia de iframes aninhados exigiria mais sinal
do que `origin`/`selector` sozinhos oferecem, e nenhuma especificação
textual confirmada define como fazer essa associação com segurança.
Isso é uma limitação conhecida, registrada em "Consequências", não um
comportamento escondido. Um método adicional `get_frames(page_id)`
(além do Port) expõe a árvore de frames capturada, para uso futuro do
Export Engine (`pages/<id>.json` tem `frame_tree`).

### `parent_index` liga elementos a seus pais dentro do mesmo lote

`RawElementObservation.parent_index` referencia outro item do MESMO
lote passado a `observe_elements()` (por posição, em pré-ordem — pais
antes de filhos), não um `element_id` diretamente, já que um elemento
novo ainda não tem identidade no momento em que o chamador monta o
lote. `capture_elements()` resolve isso para o `parent_element_id`
real após criar/reaproveitar cada elemento.

### `update_element()` exige um "stage" prévio

Como `update_element(element_id)` não recebe nenhum dado novo (só o
id, conforme o Port), um novo método `stage_element_update(element_id,
observation)` guarda a observação a ser aplicada; `update_element()` a
consome e publica `ElementUpdated`. Sem um `stage` pendente,
`update_element()` levanta `NoPendingElementsError` — mesmo padrão de
"nada para processar" já usado em `capture_elements()` e no
`NoPendingNavigationError` do Navigation Recorder (ADR 0006).

### Duas novas exceções em `element_exceptions.py`

Mudança aditiva, sem risco (mesmo padrão dos ADRs anteriores):

- `NoPendingElementsError` — `capture_elements()`/`update_element()`
  chamados sem uma observação/stage anterior.
- `ElementNotFoundError` — `update_element()`/`remove_element()`
  referenciam um `element_id` nunca capturado.

`ElementCaptureError` e `ShadowDomUnsupportedError` (já existentes)
não são usados por este módulo — pertencem a quem de fato inspeciona o
DOM (o futuro coletor assíncrono), não a este catálogo síncrono.

## Testes

`tests/unit/modules/elements/test_element_recorder.py`: captura sem
observação pendente, construção e publicação de eventos, classificação
por tipo de input/role/tag, prioridade de `role` sobre `tag`, tipo
`UNKNOWN` para tags desconhecidas, `semantic_type_hint`,
`is_sensitive_hint`, eventos de detecção especial
(`FormDetected`/`GridDetected`/`RelatedListDetected`), resolução de
`parent_index`, deduplicação por fingerprint entre capturas
sucessivas, frames distintos por origem/seletor, busca por id/
fingerprint, atualização com e sem `stage_element_update()`, remoção,
`clear_page()` isolado por página e `get_statistics()`.

## Consequências

- `snkb record`: o contador "Elementos" ainda não reflete captura
  real — falta o Application Controller coletar atributos de DOM via
  Playwright (assíncrono) e encaminhá-los para `observe_elements()` +
  `capture_elements()` (ver checklist em `docs/module-specs/README.md`).
- Classificação de tipos específicos do ServiceNow
  (`WORKSPACE_COMPONENT`, `NOW_EXPERIENCE_COMPONENT` etc.) depende
  inteiramente de `semantic_type_hint` fornecido por quem tem
  conhecimento real da estrutura do ServiceNow — não há heurística
  automática hoje.
- `Frame.parent_frame_id` nunca é preenchido — árvore de frames é
  sempre "achatada" (todos os frames de uma página são irmãos). Deve
  ser revisitado quando houver sinal confiável de aninhamento vindo do
  Browser Manager ou do coletor de DOM.
- Selector Analyzer (Capítulo 7, próximo módulo) consumirá
  `get_elements(page_id)` para gerar seletores; nenhuma mudança
  esperada neste módulo para isso.
