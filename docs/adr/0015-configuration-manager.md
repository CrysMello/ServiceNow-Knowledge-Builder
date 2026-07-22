# ADR 0015 — Configuration Manager

## Status

Aceito — 2026-07-21.

## Contexto

`bootstrap.py` sempre precisou de uma `AppConfig` para existir, mas
desde o ADR 0012 usava um carregador mínimo (`_load_config()`): lia
`config/local.json` (se existisse) ou `config/default.json` e validava
via `AppConfig.model_validate_json()` — suficiente para o Application
Controller poder ser construído, mas deliberadamente **não** uma
implementação de `ConfigurationProviderPort`
(`application/ports/configuration_provider_port.py`, já existente
desde o scaffold original): sem recarregamento em tempo de execução
nem mensagens de erro por campo (CFG-006). `snkb config` continuava
chamando `announce_pending` por essa razão, o último dos cinco
comandos "casca" do projeto.

## Decisão

### `JsonConfigurationProvider` implementa `ConfigurationProviderPort`

`infrastructure/configuration/configuration_manager.py`:

```python
class JsonConfigurationProvider:
    def __init__(self, candidates: Sequence[Path]) -> None: ...
    def load(self) -> AppConfig: ...
    def reload(self) -> AppConfig: ...
```

`load()` resolve o primeiro candidato existente (mesma ordem que
`bootstrap._load_config()` já usava:
`config/local.json`, depois `config/default.json`) e valida via
`AppConfig.model_validate_json()`. Em `pydantic.ValidationError`,
converte para `InvalidConfigurationError` (já existia em
`domain/exceptions/configuration_exceptions.py`, reservada desde o
scaffold original, nunca levantada até este ADR) com uma mensagem que
lista **cada campo** inválido e o motivo — construída a partir de
`error.errors()` (`loc`/`msg`/`input`), nunca o traceback bruto do
Pydantic (CFG-006). Nenhum candidato existente → `ConfigurationError`
com a mesma mensagem explicativa que `bootstrap._load_config()` já
tinha (copiada, não perdida): copie `config/default.json` para
`config/local.json` e ajuste `instance_url`/`output_directory`.

`reload()` simplesmente executa `load()` de novo — o adaptador não
guarda nenhum estado (nenhum cache a invalidar), então "recarregar em
tempo de execução" é só reler o disco a cada chamada. Mantém o
adaptador sem estado, coerente com o resto do projeto (nenhum outro
módulo central guarda cache que precise de invalidação explícita).

### Nova consulta: `GetEffectiveConfiguration`

`application/queries/queries.py`: `GetEffectiveConfiguration()` (sem
campos). `ApplicationController` ganha um quarto parâmetro obrigatório
no construtor, `config: AppConfig`, guardado em `self._config` e
devolvido diretamente por essa consulta — a mesma instância que
`bootstrap.py` já usa para construir todos os outros adaptadores
(Browser Manager, Screenshot Engine, Export Engine, ...), então
"configuração efetiva" reflete exatamente o que está em uso, não uma
segunda leitura independente do disco.

### `bootstrap.py`: `_load_config()` removido

`create_controller()` agora chama
`JsonConfigurationProvider(candidates=_CONFIG_CANDIDATES).load()`
diretamente — o carregador mínimo apontado como provisório desde o
ADR 0012 deixa de existir.

### `snkb config`

`presentation/cli/commands/config.py`: `create_controller()` dentro de
try/except (mesmo padrão de todos os outros comandos, desde
`record.py`), `query(GetEffectiveConfiguration())`, formatado por
`presentation/cli/formatters/config_formatter.py` — uma linha por
campo de topo de `AppConfig`, mais dois blocos indentados para
`capture_policy`/`login_detection`.

## Testes

`tests/unit/infrastructure/configuration/test_configuration_manager.py`:
config válida, ordem de resolução entre candidatos, candidato ausente
cai para o próximo, nenhum candidato existente (`ConfigurationError`),
campo inválido nomeado na mensagem (`resolution_width` negativo,
`instance_url` em branco), `reload()` relê o disco após uma mudança no
arquivo.

`tests/contract/test_ports.py`: `ConfigurationProviderPort` expõe
exatamente `load`/`reload`.

`tests/unit/presentation/cli/test_config_command.py`: configuração
efetiva impressa (incluindo `capture_policy`/`login_detection`),
arquivo de configuração ausente falha de forma limpa, campo inválido
aparece na mensagem de erro exibida ao usuário.

`tests/acceptance/test_local_recording_flow.py`: estendido (mesma
mudança do ADR 0014) para invocar `snkb config` via `CliRunner` após
uma gravação real e confirmar que a `instance_url` usada na gravação
aparece na configuração efetiva impressa.

## Consequências

- **`snkb config` funciona**: mostra a configuração efetiva
  (incluindo as políticas de captura e detecção de login) e recusa
  configuração inválida com uma mensagem por campo, nunca um
  traceback bruto do Pydantic.
- Com este ADR, os cinco comandos "casca" do projeto
  (`status`/`validate`/`open`/`logs`/`config`) estão todos
  implementados — ver ADR 0014 para os quatro primeiros.
- "Recarregamento em tempo de execução" (CFG-006) existe no sentido de
  `reload()` sempre reler o disco, mas nenhum comando da CLI hoje
  chama `reload()` depois do processo já estar rodando — cada
  invocação de `snkb config` já é um processo novo, então `load()` já
  é suficiente na prática.
