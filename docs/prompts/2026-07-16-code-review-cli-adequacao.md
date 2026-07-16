# Prompt — Code Review e Adequação para CLI

> Preservado como registro do briefing que originou o ADR 0003
> (Adequação da camada de apresentação para CLI). Recebido em
> 2026-07-16, executado via plan mode (diagnóstico → plano aprovado →
> implementação), resultado documentado em
> [`docs/adr/0003-cli-presentation-layer.md`](../adr/0003-cli-presentation-layer.md).
> Texto do prompt original preservado sem edição abaixo; o checklist
> de desbloqueio por módulo foi adicionado como anexo ao final.

---

Você é um Software Architect Sênior e Code Reviewer especialista em Python, Clean Architecture, SOLID, Playwright, aplicações CLI e refatoração segura.

Sua missão é revisar o projeto existente **ServiceNow Knowledge Builder** e adequá-lo ao modelo de uso via terminal, preservando tudo o que já estiver correto.

## Contexto do projeto

O ServiceNow Knowledge Builder será utilizado inicialmente como uma aplicação CLI.

Fluxo esperado:

1. O usuário executa o comando `snkb record`.
2. O navegador é aberto.
3. O usuário realiza login manual no ServiceNow utilizando a conta Microsoft.
4. O usuário navega normalmente pelas telas.
5. O sistema registra fluxos, páginas, elementos, seletores, screenshots e dependências.
6. Ao finalizar, o usuário retorna ao terminal e pressiona `Enter` ou interrompe a gravação de forma segura.
7. O sistema exporta a Base de Conhecimento em arquivos JSON, logs e screenshots.

A versão atual do projeto pode ter sido estruturada inicialmente para uma interface gráfica desktop.

A revisão deve adaptar somente o que for necessário para a versão CLI.

## Documentações obrigatórias

Leia integralmente os documentos anexados antes de analisar o código:

* Product Vision;
* Software Requirements Specification — SRS;
* Software Architecture Document — SAD;
* Business Rules;
* Module Specifications;
* AI Coding Standards.

Considere a documentação como fonte oficial do projeto.

Caso exista conflito entre a documentação antiga, orientada a GUI, e esta definição de uso via CLI, prevalece esta definição para a camada de apresentação.

## Objetivo da revisão

Revisar toda a arquitetura existente e identificar:

* o que está correto e deve ser preservado;
* o que está acoplado a uma interface gráfica;
* o que precisa ser removido;
* o que precisa ser renomeado;
* o que precisa ser movido;
* o que precisa ser criado;
* o que precisa ser refatorado para suportar CLI;
* o que não deve ser alterado.

## Regra principal

Não reescreva o projeto inteiro.

Não destrua a arquitetura existente.

Não altere módulos que já estejam corretos.

Não implemente funcionalidades fora do escopo.

Aplique apenas as mudanças necessárias para adequar a camada de apresentação ao uso via terminal.

## Arquitetura esperada

A arquitetura principal deverá continuar seguindo Clean Architecture.

Estrutura de referência:

```text
src/
├── application/
├── domain/
├── infrastructure/
├── presentation/
│   └── cli/
│       ├── commands/
│       ├── formatters/
│       ├── handlers/
│       └── main.py
├── shared/
└── bootstrap/
```

A estrutura real poderá variar caso a documentação oficial já determine outra organização, desde que:

* a camada CLI permaneça isolada;
* a lógica de negócio não fique dentro dos comandos;
* a infraestrutura não dependa da apresentação;
* o domínio não dependa de Playwright ou da CLI;
* não existam dependências circulares.

## Alterações esperadas

Analise se é necessário:

* remover PySide6, CustomTkinter ou outra dependência de GUI;
* remover diretórios exclusivos de interface desktop;
* substituir `UI Manager` por `CLI Controller`, `Command Handler` ou nome equivalente;
* criar comandos CLI;
* criar ponto de entrada executável;
* configurar o comando `snkb`;
* ajustar `pyproject.toml`;
* ajustar dependências;
* ajustar bootstrap da aplicação;
* ajustar encerramento seguro;
* preservar exportação parcial em caso de interrupção;
* preservar logs;
* preservar regras de segurança;
* preservar login manual via Microsoft;
* preservar os módulos centrais existentes.

## Comandos mínimos

A aplicação deverá estar preparada para suportar:

```bash
snkb record
snkb status
snkb validate
snkb open
snkb logs
snkb config
snkb version
```

Para o MVP, o comando principal será:

```bash
snkb record
```

Fluxo esperado do comando:

```text
Inicializar aplicação
→ validar configuração
→ abrir navegador
→ aguardar login manual Microsoft
→ iniciar gravação
→ manter captura ativa
→ aguardar Enter ou interrupção segura
→ finalizar sessão
→ exportar arquivos
→ exibir caminho da Base de Conhecimento
```

Não implemente processo em background, daemon, socket local ou gerenciamento de PID nesta versão, salvo se isso já estiver documentado e implementado corretamente.

## Módulos que devem ser preservados

Revise e preserve, sempre que estiverem corretos:

* Browser Manager;
* Session Manager;
* Navigation Recorder;
* Element Recorder;
* Selector Analyzer;
* Screenshot Engine;
* Export Engine;
* Log Engine;
* Configuration Manager;
* Event Bus;
* modelos de domínio;
* DTOs;
* interfaces públicas;
* exceções;
* eventos;
* schemas;
* testes existentes.

A mudança de GUI para CLI não deve alterar a responsabilidade desses módulos.

## Segurança

Confirme que o projeto:

* não automatiza o login Microsoft;
* não preenche e-mail, senha ou MFA;
* não persiste senha;
* não exporta cookies;
* não armazena tokens;
* não registra dados sensíveis nos logs;
* não altera dados no ServiceNow;
* apenas observa e registra a navegação.

## Processo obrigatório

Antes de alterar o código:

1. Leia toda a documentação.
2. Analise a árvore atual do projeto.
3. Identifique as dependências existentes.
4. Identifique todos os componentes ligados à GUI.
5. Identifique quais módulos estão corretos.
6. Crie um relatório de impacto.
7. Crie um plano de alteração por arquivo.
8. Somente depois aplique as mudanças.

## Entrega esperada da análise

Apresente inicialmente:

### 1. Diagnóstico atual

* arquitetura encontrada;
* tecnologias encontradas;
* módulos existentes;
* dependências de GUI;
* riscos;
* inconsistências;
* pontos corretos.

### 2. Classificação dos arquivos

Classifique cada arquivo analisado como:

* manter;
* alterar;
* mover;
* renomear;
* remover;
* criar.

### 3. Plano de refatoração

Para cada mudança, informe:

* arquivo;
* motivo;
* impacto;
* risco;
* teste necessário.

## Regras para alteração do código

Após o diagnóstico:

* preserve contratos públicos sempre que possível;
* preserve nomes de eventos;
* preserve formatos JSON;
* preserve critérios de aceite;
* preserve regras de negócio;
* evite alterações em massa;
* não crie código duplicado;
* não use `TODO`;
* não use `pass`;
* não deixe funções vazias;
* não crie código provisório;
* utilize tipagem estática;
* utilize injeção de dependência;
* siga PEP 8;
* siga o AI Coding Standards;
* mantenha compatibilidade com Windows.

## Testes obrigatórios

Crie ou atualize testes para validar:

* inicialização da CLI;
* execução de `snkb record`;
* abertura do navegador;
* espera pelo login manual;
* início da sessão;
* encerramento ao pressionar `Enter`;
* encerramento seguro com `Ctrl+C`;
* exportação da Base de Conhecimento;
* manutenção dos dados em caso de erro;
* exibição correta de mensagens;
* ausência de dependências de GUI;
* ausência de armazenamento de credenciais.

## Critérios de aceite

A revisão será considerada concluída quando:

* o projeto puder ser executado via terminal;
* o comando `snkb record` estiver funcional;
* o navegador abrir corretamente;
* o login continuar manual;
* a gravação puder ser encerrada com segurança;
* os arquivos da Base de Conhecimento forem exportados;
* os módulos centrais forem preservados;
* dependências desnecessárias de GUI forem removidas;
* a camada CLI estiver isolada;
* todos os testes aplicáveis passarem;
* a documentação afetada for atualizada;
* nenhuma regra de negócio for violada.

## Auto Review obrigatória

Ao final, apresente:

* arquivos mantidos;
* arquivos alterados;
* arquivos criados;
* arquivos removidos;
* testes executados;
* testes aprovados;
* critérios de aceite atendidos;
* riscos restantes;
* pendências;
* comandos para instalar;
* comandos para executar;
* comandos para testar.

Não declare que a adequação foi concluída caso exista erro, teste falhando ou requisito não atendido.

Comece pela análise da arquitetura atual e não altere nenhum arquivo antes de apresentar o diagnóstico e o plano de refatoração.

---

## Anexo — Checklist de desbloqueio por módulo

> Adicionado em 2026-07-16, após a implementação do ADR 0003, em
> resposta à pergunta "esses riscos e pendências já estão mapeados nas
> implementações futuras?". A cópia viva desta tabela (a que deve ser
> atualizada conforme os módulos forem implementados) fica em
> [`docs/module-specs/README.md`](../module-specs/README.md#checklist-de-desbloqueio-na-cli-adr-0003) —
> esta cópia aqui é um retrato do momento em que o anexo foi escrito.

| Módulo (Capítulo) | Desbloqueia na CLI | Arquivo a alterar quando o módulo existir | Feito? |
| --- | --- | --- | --- |
| Browser Manager (3) | `snkb record`: abrir navegador + aguardar login manual (hoje só dispara `StartCapture` e para no `NotImplementedError` de `create_controller`) | `bootstrap.create_controller` (wiring), sem mudança em `record_handler.py` | ☐ |
| Session Manager (4) | `snkb record`: sessão de fato criada/rastreada (evento `SessionStarted`); **`snkb status`** passa a funcionar | `bootstrap.create_controller`; `presentation/cli/commands/status.py` (remover `announce_pending`, implementar consulta real via `GetSessionStatus`/`GetSessionStatistics`) | ☐ |
| Navigation Recorder (5) | `snkb record`: contador "Páginas" passa a refletir navegação real (já reage a `PageCaptured`) | `bootstrap.create_controller` (wiring) | ☐ |
| Element Recorder (6) | `snkb record`: contador "Elementos" (hoje fixo em 0) | `presentation/cli/status_aggregator.py` (adicionar caso para o evento de elemento capturado) | ☐ |
| Selector Analyzer (7) | Nenhum comando CLI direto — alimenta `selectors.json`, consumido pelo Export Engine | — | ☐ |
| Screenshot Engine (8) | `snkb record`: contador "Screenshots" (hoje fixo em 0) | `presentation/cli/status_aggregator.py` (adicionar caso para `ScreenshotCreated`) | ☐ |
| Export Engine (9) | `snkb record`: exportação final e caminho da Base de Conhecimento (`ExportCompleted`/`ExportFailed` já tratados); **`snkb validate`** e **`snkb open`** passam a funcionar | `presentation/cli/commands/validate.py` e `open_folder.py` (remover `announce_pending`) | ☐ |
| Log Engine (10) | **`snkb logs`** passa a funcionar; contador "Logs" em `snkb record` | `presentation/cli/commands/logs.py` (remover `announce_pending`) | ☐ |
| Configuration Manager (SAD, não numerado no Module Specifications) | **`snkb config`** passa a funcionar; `snkb record --instance-url` passa a ter valor padrão vindo de `config/default.json` | `presentation/cli/commands/config.py`; `presentation/cli/commands/record.py` | ☐ |
| Application Controller (nenhum capítulo próprio — é o composition root) | Todos os comandos deixam de propagar `NotImplementedError` de `create_controller`; decide como eventos chegam a `RecordCommandHandler.handle_domain_event` (callback direto vs. Protocol de assinatura — decisão adiada no ADR 0003) | `bootstrap.py` (implementação real de `create_controller`) | ☐ |
