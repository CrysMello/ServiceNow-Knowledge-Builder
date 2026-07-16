# Documentation index

| Document | Purpose | Location |
| --- | --- | --- |
| 00 — Product Vision | Scope, goals, roadmap | maintained outside this repo; add under `docs/` when versioned |
| 01 — SRS | Functional/non-functional requirements, use cases, acceptance criteria | same |
| 02 — SAD | Layered architecture, components, dependencies | `docs/architecture/README.md` mirrors it for this codebase |
| 03 — Business Rules | What may/may not be recorded, security rules (RN-xxx, RS-xxx) | same |
| 04 — Test Cases | Test cases for the Knowledge Builder itself | `tests/` implements this once modules exist |
| 05 — AI Development Guide | Step-by-step module build order and Prompt Mestre | drives the order modules are implemented in |
| 06 — AI Coding Standards | Mandatory coding rules for any contributor (human or AI) | this scaffold follows it throughout |
| Module Specifications | Per-module responsibilities, interfaces, events, exceptions | `docs/module-specs/README.md` |
| Prompts | Verbatim briefs that drove a refactor/ADR, preserved for reference | `docs/prompts/` |

See [architecture/README.md](architecture/README.md) for how the
`src/snkb` package maps onto the SAD, and
[adr/0001-project-scaffolding.md](adr/0001-project-scaffolding.md) for
what this initial commit deliberately does and does not contain.

The CLI presentation layer (ADR 0003) has a per-module "unlocks in the
CLI" checklist in
[module-specs/README.md](module-specs/README.md#checklist-de-desbloqueio-na-cli-adr-0003) —
check it off as each central module (Browser Manager, Session Manager,
...) is implemented, so the corresponding CLI command gets wired up in
the same step instead of being forgotten.
