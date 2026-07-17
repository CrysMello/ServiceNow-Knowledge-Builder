# ADR 0011 — Implementação do Log Engine

## Status

Aceito — 2026-07-17.

## Contexto

Oitavo e último módulo central de dados do projeto antes do
Application Controller (Module Specifications, Capítulo 10; AI
Development Guide, etapa 11), depois do Browser Manager (ADR 0004),
Session Manager (ADR 0005), Navigation Recorder (ADR 0006), Element
Recorder (ADR 0007), Selector Analyzer (ADR 0008), Screenshot Engine
(ADR 0009) e Export Engine (ADR 0010). Diferente dos seis módulos
`modules/*` (Session a Export), o Log Engine vive em
`infrastructure/logging/` — o próprio pacote já estava reservado
assim desde o scaffolding inicial (ADR 0001), com a nota "backed by
Loguru... per the stack decision in AI Coding Standards, section 4".
Isso é consistente com o Browser Manager: ambos são adaptadores que
envolvem uma biblioteca de terceiros (Playwright / Loguru), então só
`infrastructure/` pode importá-la — nenhum outro módulo já implementado
grava logs diretamente, todos recebem `LogEnginePort` por injeção de
dependência e já chamam `self._log.info(...)` etc.

`LogEnginePort` não tem nenhum evento de domínio próprio nem depende
de `EventPublisherPort` — é ele mesmo o mecanismo de registro usado
por todos os outros, não um publicador de eventos.

## Decisão

### Registro em memória, espelhado em arquivo via Loguru

Cada chamada (`trace`/`debug`/`info`/`warning`/`error`/`critical`/
`exception`) faz duas coisas: (1) acrescenta um `dict` estruturado a
uma lista interna (`_entries`), e (2) delega ao Loguru real
(`logger.bind(**context).log(nível, mensagem)`) para persistência em
arquivo. `export()`/`statistics()` operam exclusivamente sobre a lista
em memória — nunca reabrem nem reanalisam o arquivo de log — então a
correção desses dois métodos não depende de nenhum detalhe de
formatação do Loguru.

### Uso direto do logger global do Loguru, sem duplo de teste

Ao contrário do Browser Manager (que precisou de injeção de
dependência para evitar abrir um Chromium real na maioria dos testes),
o Loguru é uma biblioteca Python pura, rápida e determinística — não
há processo externo, rede ou navegador envolvido. Por isso os testes
usam o `logger` real do Loguru diretamente, com `tmp_path` do pytest
como diretório de log; não foi necessário nenhum duplo de teste. Para
evitar acumular *sinks* entre instâncias (o `logger` do Loguru é um
singleton por módulo), o construtor sempre chama `logger.remove()`
antes de adicionar o seu próprio *sink* — isso também garante que cada
teste, ao criar uma nova instância, comece de um estado limpo.

### Filtragem por nível é responsabilidade deste módulo, não do Loguru

`AppConfig.log_level` (padrão `"info"`) determina o piso de
severidade: chamadas abaixo desse nível (ex.: `trace()`/`debug()`
quando configurado para `"warning"`) são descartadas antes de tocar
tanto a lista em memória quanto o Loguru — nenhuma chamada suprimida
aparece em `export()`/`statistics()` nem no arquivo. Isso reproduz a
semântica padrão de bibliotecas de log (um piso de severidade, não um
filtro por mensagem).

### `exception()` sempre registra em nível `error`

Segue a mesma convenção do `logging.Logger.exception()` do Python:
deve ser chamado de dentro de um bloco `except`, anexando o traceback
corrente via `logger.opt(exception=True)`. Chamar fora de um `except`
não lança erro, mas não terá um traceback real para anexar — mesma
limitação inerente do equivalente na biblioteca padrão, documentada na
docstring do método, não escondida.

### Chaves de contexto nunca sobrescrevem `timestamp`/`level`/`message`

O `dict` de contexto (`**context`) é espalhado **antes** das três
chaves reservadas na construção do registro. Na prática, `message=`
já é o parâmetro posicional de cada método (o Python rejeita a
chamada antes mesmo de chegar à lógica interna); `level=` é o único
colisão realmente alcançável via contexto (já que o nível vem
implícito do nome do método, não de um parâmetro nomeado) — e mesmo
assim o valor real sempre prevalece. Testado explicitamente
(`test_context_cannot_shadow_the_level_key`).

### Retenção e nível vêm de `AppConfig`, mas são passados diretamente

O construtor recebe `log_level: str` e `retention_days: int`
diretamente (mesmo padrão de outros módulos que recebem só o que
precisam de `AppConfig`, não o objeto inteiro). Nível inválido levanta
a nova `InvalidLogLevelError` (`domain.exceptions.log_exceptions`) —
único arquivo de exceções novo desta etapa, seguindo o padrão de todos
os módulos anteriores.

## Testes

`tests/unit/infrastructure/logging/test_log_engine.py`: nível de log
inválido na construção, criação do diretório de log, cada um dos seis
métodos de nível grava uma entrada correta, contexto não sobrescreve
chaves reservadas, `exception()` registra em nível `error` com
traceback real, mensagens abaixo do nível configurado são descartadas,
`flush()` não lança mesmo sem entradas, `export()` retorna cópias
independentes (mutar o resultado não afeta o estado interno),
`statistics()` agrega por nível, e um teste de persistência real
confirmando que o arquivo `.log` é de fato criado em disco com o
conteúdo esperado.

## Consequências

- `snkb logs` ainda não funciona ponta a ponta — falta o Application
  Controller instanciar `LoguruLogEngine` e injetá-lo em todos os
  demais módulos (`bootstrap.create_controller`; ver checklist em
  `docs/module-specs/README.md`).
- `statistics()["total_entries"]` poderá alimentar
  `StatisticsJsonModel.total_logs` (hoje fixo em `0` no Export Engine,
  ADR 0010) assim que o Application Controller conectar os dois
  módulos — nenhuma mudança é necessária em nenhum dos dois lados.
- Com a implementação deste módulo, todos os oito módulos centrais dos
  Capítulos 3 a 10 (Browser Manager, Session Manager, Navigation
  Recorder, Element Recorder, Selector Analyzer, Screenshot Engine,
  Export Engine, Log Engine) estão implementados e testados
  isoladamente. Resta apenas o Application Controller — o composition
  root que efetivamente os conecta uns aos outros e à CLI.
