# ServiceNow Knowledge Builder

Aplicação de linha de comando (`snkb`) que observa uma sessão
autenticada do ServiceNow e produz uma **Base de Conhecimento**
estruturada e reutilizável — páginas, elementos, seletores, grafo de
navegação, screenshots e relatórios — para consumo futuro pelo **QA
ServiceNow Assistant**.

O Knowledge Builder nunca automatiza ações de negócio do ServiceNow,
nunca preenche formulários, nunca clica em nome do usuário, e nunca
automatiza ou armazena credenciais, códigos MFA ou tokens do Microsoft
Entra ID (SSO). A autenticação é sempre manual. Ver `RS-001` a
`RS-015` no documento de Regras de Negócio para a lista completa de
garantias de segurança.

## Status

O scaffold arquitetural (estrutura de pacotes, modelos de domínio,
ports, DTOs, exceções, eventos, configuração — ver
[docs/adr/0001-project-scaffolding.md](docs/adr/0001-project-scaffolding.md))
e a camada de apresentação da CLI (ver
[docs/adr/0003-cli-presentation-layer.md](docs/adr/0003-cli-presentation-layer.md))
estão implementados. Todos os oito módulos centrais dos Capítulos 3–10
do Module Specifications também estão implementados e conectados
(Browser Manager, Session Manager, Navigation Recorder, Element
Recorder, Selector Analyzer, Screenshot Engine, Export Engine, Log
Engine — ADRs 0004–0011), junto com o `ApplicationController`
(ADR 0012) e o Browser Data Collector (ADR 0013), que fecha o pipeline
ponta a ponta com dados reais.

`snkb record --instance-url ...` já funciona de ponta a ponta: abre um
Chromium real, aguarda o login manual, rastreia a navegação, coleta
elementos reais de DOM, gera seletores, captura screenshots e exporta
uma Base de Conhecimento completa ao encerrar. `snkb --help`,
`snkb version` e os demais comandos "pendentes" (`status`, `validate`,
`open`, `logs`, `config`) continuam chamando `announce_pending` — eles
dependem de um mecanismo de descoberta da sessão mais recente em disco
(cada invocação da CLI é um processo novo) ou do Configuration
Manager, nenhum dos dois implementado ainda (ver ADR 0012/0013,
"Consequências").

## Fonte da verdade

A implementação deve sempre ser rastreável a estes documentos,
consultados nesta ordem de autoridade (AI Coding Standards, seção 2):

1. Product Vision
2. Software Requirements Specification (SRS)
3. Business Rules
4. Software Architecture Document (SAD)
5. Module Specifications
6. Interface Contracts
7. AI Coding Standards

## Arquitetura

Clean Architecture com quatro camadas, cada uma dependendo apenas da
camada abaixo dela:

```
presentation  → application → domain
infrastructure → application/domain (ports)
```

Ver [docs/architecture/README.md](docs/architecture/README.md) para o
mapa completo de diretórios e a responsabilidade de cada pacote.

## Primeiros passos

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows
pip install -e ".[dev]"
playwright install chromium
```

Rodar a suíte de testes:

```bash
pytest
ruff check .
black --check .
mypy src
```

## Uso

```bash
snkb --help              # lista os 7 comandos
snkb version             # imprime a versão instalada
snkb record --instance-url https://sua-instancia.service-now.com
snkb status              # status da sessão (pendente: precisa de descoberta em disco)
snkb validate             # verificação de integridade da Base de Conhecimento (pendente)
snkb open                 # abre a pasta de exportação (pendente)
snkb logs                  # logs da sessão (pendente)
snkb config                 # configuração efetiva (pendente: precisa do Configuration Manager)
```

`snkb record` abre o navegador, aguarda o login manual via Microsoft,
grava a navegação e encerra com segurança ao pressionar `Enter` ou
`Ctrl+C`, exportando a Base de Conhecimento para
`exports/<session-id>/`. Ver
[docs/adr/0003-cli-presentation-layer.md](docs/adr/0003-cli-presentation-layer.md)
para o fluxo completo de comandos e
[docs/adr/0013-browser-data-collector.md](docs/adr/0013-browser-data-collector.md)
para como os dados reais são coletados e exportados.

## Estrutura do repositório

```
src/snkb/           Código-fonte da aplicação (ver docs/architecture)
tests/               unitários, integração, contrato, aceite
docs/                notas de arquitetura, ADRs, module specifications
schemas/             JSON Schemas dos artefatos exportados
config/              configuração padrão da aplicação
exports/             saída das sessões (nunca versionado)
logs/                logs de sessão (nunca versionado)
examples/            exemplos de uso
scripts/             ferramentas de desenvolvimento
```

## Roteiro

A camada de apresentação da CLI está concluída (ADR 0003), assim como
os oito módulos centrais e o Application Controller (ADRs 0004–0012) e
o Browser Data Collector (ADR 0013), que fecha o pipeline ponta a
ponta com dados reais. Os próximos passos são os comandos que
dependem de descoberta de sessão em disco (`status`/`validate`/`open`/
`logs`) e o Configuration Manager (`config`).
