# ADR 0008 — Implementação do Selector Analyzer

## Status

Aceito — 2026-07-17.

## Contexto

Quinto módulo central do projeto (Module Specifications, Capítulo 7;
AI Development Guide, etapa 8), depois do Browser Manager (ADR 0004),
Session Manager (ADR 0005), Navigation Recorder (ADR 0006) e Element
Recorder (ADR 0007). Diferente de todos os anteriores, este módulo
**não precisa de nenhuma observação bruta externa**: os atributos
necessários para gerar seletores (`html_id`, `name`, `accessible_name`,
`label`, `role`, `tag`, `classes`, `parent_element_id`) já foram
capturados e classificados pelo Element Recorder. Por isso sua única
dependência declarada é `ElementRecorderPort` (`modules/selectors/
__init__.py`, 7.5) — sem I/O, sem Playwright, sem observação própria.

## Decisão

### Sem `data_testid`: a entidade `Element` não captura esse atributo

`SelectorStrategyType.DATA_TESTID` existe no enum, mas `Element`
(domain) e `RawElementObservation` (Element Recorder, ADR 0007) não
têm nenhum campo para um atributo `data-testid`. Gerar esse candidato
exigiria fabricar um dado que não existe na cadeia de captura atual.
`generate()` simplesmente nunca produz um candidato `DATA_TESTID` —
registrado como limitação conhecida (ver "Consequências"), não
escondido. Se o Element Recorder ganhar esse atributo no futuro, este
módulo passa a gerar o candidato automaticamente, sem nenhuma mudança
de contrato.

### Geração usa apenas semântica genérica de web, mais os "irmãos" da página

Para cada estratégia com sinal disponível (`ID`, `NAME`, `ARIA_LABEL`,
`ROLE`), o valor do `uniqueness_count` é calculado comparando o
elemento com os demais elementos da MESMA página
(`element_recorder.get_elements(page_id)`) — uso direto e justificado
da dependência declarada em 7.5. Um `id` duplicado, por exemplo, reduz
a confiança do candidato de 95 para 40 e dispara `SelectorConflict`
durante `analyze()`.

`CSS`, `XPATH_RELATIVE` e `XPATH_ABSOLUTE` são sempre gerados —
`tag` é um campo obrigatório e não vazio de `Element`, então sempre
existe pelo menos um fallback, por mais fraco que seja
(`XPATH_ABSOLUTE` com confiança 15). Isso significa que
`NoViableSelectorError` ("todo candidato é inválido") na prática
quase nunca é levantado — está implementado corretamente pelo
contrato do Port, mas é um caminho residual, já documentado.

`XPATH_ABSOLUTE` percorre a cadeia `parent_element_id` (já preenchida
pelo Element Recorder via `parent_index`, ADR 0007), construindo um
caminho `/tag_avô/tag_pai/tag`. Limitado a
`_MAX_XPATH_DEPTH = 50` para nunca entrar em loop, mesmo diante de
dados corrompidos.

### `calculate_score()` combina prioridade da estratégia, confiança e estabilidade

```
score = peso_da_estratégia * 0.4 + confidence_score * 0.4 + stability_score * 0.2
```

O peso por estratégia (`ID=100 … XPATH_ABSOLUTE=10`) reproduz
diretamente a ordem de prioridade documentada no próprio enum
`SelectorStrategyType` (RN-010, RN-011: "ordered by priority"). Essa é
a única fonte usada para o peso — não foi inventado nenhum número sem
respaldo textual. `generate()` ordena os candidatos por este score
(não pela propriedade `ElementSelectors.best_candidate`, que usa só
`confidence_score` bruto) — `get_best_selector()` também usa esta
ordenação, garantindo consistência entre os dois.

### `analyze()` calcula e persiste; `generate()` só calcula

`generate(element_id)` é uma função pura (sem publicar eventos, sem
guardar estado) — pode ser chamada repetidamente sem efeito colateral,
inclusive por `validate_selector()` indiretamente. `analyze()` chama
`generate()`, guarda o resultado em `ElementSelectors`, e publica
`SelectorsReady` sempre, mais `LowConfidenceSelector` (quando o melhor
candidato pontua abaixo de 50) e `SelectorConflict` (quando o
candidato `ID` tem `uniqueness_count > 1`) condicionalmente.

### `register_session_for_page()`, novamente

Nenhum método do Port recebe `session_id` (só `element_id`), mas todo
evento publicado precisa dele. Mesma solução do Element Recorder (ADR
0007) e do Navigation Recorder (ADR 0006): um método adicional,
`register_session_for_page(session_id, page_id)`, que o futuro
Application Controller chamará uma vez por página. Sem essa chamada
prévia, `analyze()`/`update_selector()` levantam a nova
`PageSessionNotRegisteredError`.

### `get_all_selectors()`/`get_best_selector()` calculam sob demanda

Ao contrário dos outros módulos ("nada pendente" levanta exceção),
aqui uma consulta a um elemento ainda não analisado simplesmente
chama `analyze()` internamente e retorna o resultado — decisão
deliberada: como `generate()` é barato e sempre disponível (não
depende de nenhuma observação externa pendente), exigir uma chamada
explícita a `analyze()` antes de toda consulta seria apenas
burocracia sem benefício real. `remove_selector()`, por outro lado,
exige análise prévia (não há nada sensato para "remover" de um
elemento nunca analisado) e levanta `ElementNotFoundError` nesse caso
— reaproveitado do Element Recorder (ADR 0007) em vez de criar mais um
tipo de exceção para o mesmo conceito ("elemento sem estado
conhecido").

### Uma nova exceção em `selector_exceptions.py`

- `PageSessionNotRegisteredError` — `analyze()`/`update_selector()`
  chamados antes de `register_session_for_page()` para a página do
  elemento.

## Testes

`tests/unit/modules/selectors/test_selector_analyzer.py`: elemento/
sessão desconhecidos, geração de um candidato por sinal disponível,
ranking do `ID` como melhor estratégia quando único, conflito de `id`
duplicado (confiança menor + `SelectorConflict`), fallback completo
para um elemento só com `tag`, XPath absoluto com cadeia de pais,
`calculate_score()`, eventos de `analyze()`
(`SelectorsReady`/`LowConfidenceSelector`/`SelectorConflict`),
consulta preguiçosa via `get_all_selectors()`, `get_best_selector()`,
`validate_selector()` (casos válidos/inválidos/elemento desconhecido),
`update_selector()` após mudança no elemento, e `remove_selector()`
(com e sem análise prévia).

## Consequências

- Nenhum candidato `DATA_TESTID` é gerado até que o Element Recorder
  capture esse atributo — pendência explícita, não uma omissão
  silenciosa.
- `validate_selector()` só valida estruturalmente (o elemento existe,
  o valor corresponde ao atributo esperado); sem navegador real, não
  há como confirmar que o seletor realmente localiza um único nó no
  DOM vivo. Isso é inerente à arquitetura síncrona/sem I/O de todos os
  módulos centrais implementados até aqui, não uma lacuna deste módulo
  específico.
- Export Engine (Capítulo 9, futuro) consumirá `get_all_selectors()`
  por elemento para montar `selectors.json`; nenhuma mudança esperada
  neste módulo para isso.
- `bootstrap.create_controller` ainda não chama
  `register_session_for_page()` nem `analyze()` — `selectors.json`
  continua vazio na prática até essa etapa de wiring (ver checklist em
  `docs/module-specs/README.md`).
