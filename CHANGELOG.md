# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste
arquivo. O formato segue [Keep a
Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e o projeto
adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.1.0] - Não lançado

### Adicionado

- 2026-08-02: Documentação institucional do projeto — `LICENSE`,
  `AUTHORS.md`, `NOTICE`, `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `CITATION.cff`, `VERSION` — e
  metadados de autoria em `pyproject.toml`.
- 2026-07-21: Descoberta de sessão em disco, abertura de pasta de
  exportação, leitura de logs persistidos e Configuration Manager
  (comandos `status`, `open`, `logs`, `config`).
- 2026-07-17: Application Controller, orquestrando os módulos
  centrais.
- 2026-07-17: Log Engine.
- 2026-07-17: Export Engine.
- 2026-07-17: Screenshot Engine.
- 2026-07-16: Session Manager.
- 2026-07-16: Browser Manager (observação de sessão real via
  Playwright/Chromium).
- 2026-07-16: Camada de apresentação da CLI (comando `record` e os
  demais comandos da interface de linha de comando).
- 2026-07-16: Scaffold arquitetural inicial (estrutura de pacotes,
  modelos de domínio, ports, DTOs, exceções, eventos, configuração).

### Corrigido

- 2026-08-02: Contadores de elementos e screenshots no resumo ao vivo
  do comando `record`, que ficavam travados em zero mesmo quando os
  dados reais já haviam sido capturados e exportados corretamente.

### Alterado

- 2026-07-20: Tradução do `README.md` e `examples/README.md` para
  pt-BR, com atualização do status do projeto.

[0.1.0]: https://github.com/CrysMello/ServiceNow-Knowledge-Builder
