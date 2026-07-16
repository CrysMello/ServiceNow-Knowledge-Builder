# ServiceNow Knowledge Builder

Command-line application (`snkb`) that observes an authenticated
ServiceNow session and produces a structured, reusable **Knowledge
Base** — pages, elements, selectors, navigation graph, screenshots and
reports — for later consumption by the future **QA ServiceNow
Assistant**.

The Knowledge Builder never automates ServiceNow business actions,
never fills forms, never clicks on the user's behalf, and never
automates or stores Microsoft Entra ID (SSO) credentials, MFA codes or
tokens. Authentication is always manual. See `RS-001` through `RS-015`
in the Business Rules document for the full list of security
guarantees.

## Status

The architectural scaffold (package structure, domain models, ports,
DTOs, exceptions, events, configuration — see
[docs/adr/0001-project-scaffolding.md](docs/adr/0001-project-scaffolding.md))
and the CLI presentation layer (see
[docs/adr/0003-cli-presentation-layer.md](docs/adr/0003-cli-presentation-layer.md))
are implemented. `snkb --help`, `snkb version` and the 5 "pending"
commands (`status`, `validate`, `open`, `logs`, `config`) work today.
`snkb record` runs its full flow but fails with a clear message at the
point where it needs a core module (Browser Manager, Session Manager,
...) that is not implemented yet — none of the central modules
(Browser Manager, Session Manager, Navigation Recorder, Element
Recorder, Selector Analyzer, Screenshot Engine, Export Engine, Log
Engine) has business logic yet.

## Source of truth

Implementation must always be traceable to these documents, consulted
in this order of authority (AI Coding Standards, section 2):

1. Product Vision
2. Software Requirements Specification (SRS)
3. Business Rules
4. Software Architecture Document (SAD)
5. Module Specifications
6. Interface Contracts
7. AI Coding Standards

## Architecture

Clean Architecture with four layers, each depending only on the one
below it:

```
presentation  → application → domain
infrastructure → application/domain (ports)
```

See [docs/architecture/README.md](docs/architecture/README.md) for the
full directory map and the responsibility of every package.

## Getting started

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows
pip install -e ".[dev]"
playwright install chromium
```

Run the test suite:

```bash
pytest
ruff check .
black --check .
mypy src
```

## Usage

```bash
snkb --help              # lists all 7 commands
snkb version             # prints the installed version
snkb record --instance-url https://your-instance.service-now.com
snkb status              # session status (pending: needs Session Manager)
snkb validate             # Knowledge Base integrity check (pending: needs Export Engine)
snkb open                 # opens the export folder (pending: needs Export Engine)
snkb logs                  # session logs (pending: needs Log Engine)
snkb config                 # effective configuration (pending: needs Configuration Manager)
```

`snkb record` opens the browser, waits for manual Microsoft login,
records the navigation, and stops safely on `Enter` or `Ctrl+C`,
exporting the Knowledge Base. See
[docs/adr/0003-cli-presentation-layer.md](docs/adr/0003-cli-presentation-layer.md)
for the full command flow.

## Repository layout

```
src/snkb/           Application source (see docs/architecture)
tests/               unit, integration, contract, acceptance
docs/                architecture notes, ADRs, module specifications
schemas/             JSON Schemas for exported artifacts
config/              default application configuration
exports/             session output (never versioned)
logs/                session logs (never versioned)
examples/            usage examples, added once modules exist
scripts/             developer tooling
```

## Roadmap

The CLI presentation layer is done (ADR 0003). Development now
proceeds module by module, per the AI Development Guide: Browser
Manager → Session Manager → Navigation Recorder → Element Recorder →
Selector Analyzer → Screenshot Engine → Export Engine → Log Engine →
integration → tests → traceability validation.
