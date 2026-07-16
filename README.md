# ServiceNow Knowledge Builder

Desktop application that observes an authenticated ServiceNow session
and produces a structured, reusable **Knowledge Base** — pages,
elements, selectors, navigation graph, screenshots and reports — for
later consumption by the future **QA ServiceNow Assistant**.

The Knowledge Builder never automates ServiceNow business actions,
never fills forms, never clicks on the user's behalf, and never
automates or stores Microsoft Entra ID (SSO) credentials, MFA codes or
tokens. Authentication is always manual. See `RS-001` through `RS-015`
in the Business Rules document for the full list of security
guarantees.

## Status

This repository currently contains **only the architectural scaffold**:
package structure, domain models, ports (interfaces), DTOs, exceptions,
events and configuration — no module has business logic yet. See
[docs/adr/0001-project-scaffolding.md](docs/adr/0001-project-scaffolding.md)
for what was deliberately left unimplemented and why.

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

Development proceeds module by module, per the AI Development Guide:
Browser Manager → Session Manager → Navigation Recorder → Element
Recorder → Selector Analyzer → Screenshot Engine → Export Engine → Log
Engine → UI Manager → integration → tests → traceability validation.
