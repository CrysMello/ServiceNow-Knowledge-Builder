# ADR 0001 — Project scaffolding only, no module logic

## Status

Accepted — 2026-07-16.

## Context

The project has six governing documents (Product Vision, SRS, Business
Rules, SAD, Module Specifications, AI Coding Standards) but no code.
Before any module (Browser Manager, Session Manager, Navigation
Recorder, Element Recorder, Selector Analyzer, Screenshot Engine,
Export Engine, Log Engine, UI Manager) is implemented, the repository
needs a Clean Architecture skeleton that later development steps can
fill in without restructuring.

## Decision

This first commit creates only:

- the full directory tree for `presentation`, `application`, `domain`,
  `infrastructure`, `modules` and `shared`;
- domain entities, value objects, enums, events and exceptions (pure
  data, matching the JSON schemas in SRS section 10 and the module
  specs' "Eventos Publicados" / "Tratamento de Exceções" sections);
- `application/ports`: one `Protocol` per module's documented "Interface
  Pública", with method signatures only;
- `shared/dtos`: Pydantic v2 models for every exported artifact and for
  `AppConfig`;
- `bootstrap.py`, whose `create_application()` raises
  `NotImplementedError` with a message naming the missing modules,
  instead of returning a non-functional application silently;
- test scaffolding: unit tests for the data structures above (they are
  data, not modules, so they are safe to exercise now), a contract
  suite asserting each port's method set matches its Module
  Specification, and README placeholders for integration/acceptance
  suites that require real modules;
- root tooling: `pyproject.toml`, `requirements.txt`, `.gitignore`,
  `README.md`, plus `config/`, `schemas/`, `exports/`, `logs/`,
  `examples/`, `scripts/` directories.

No Browser Manager, Session Manager, Navigation Recorder, Element
Recorder, Selector Analyzer, Screenshot Engine, Export Engine, Log
Engine or UI Manager class was implemented. Each `modules/<name>/`
and `infrastructure/<name>/` package contains only a docstring naming
the port it will fulfill and the Module Specification chapter that
governs it.

## Consequences

- `bootstrap.create_application()` cannot be called successfully yet;
  this is intentional (PR-007: fail loudly, not silently).
- Every subsequent development step (AI Development Guide, etapas
  4-11) has an established location to add its concrete class and can
  import the matching port from `application.ports` without touching
  this scaffold.
- `mypy --strict` and `ruff` can run against this scaffold today, so CI
  can be wired up before any module lands.
