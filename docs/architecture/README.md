# Architecture map

This scaffold implements the layered structure defined in the Software
Architecture Document (SAD) and AI Coding Standards, section 6.

```
src/snkb/
├── presentation/          CLI (`snkb <command>`). No business rules (ADR 0003).
│   └── cli/
│       ├── main.py          Typer app; registers the 7 minimum commands.
│       ├── state.py          RecordingState (recording lifecycle).
│       ├── view_models.py     SessionInfo, RecordingCounters, LogEntry.
│       ├── event_queue.py      DomainEventQueue (thread-safe bridge).
│       ├── state_machine.py    RecordingStateMachine.
│       ├── status_aggregator.py RecordingCounterAggregator.
│       ├── commands/           One thin Typer function per subcommand.
│       ├── handlers/            RecordCommandHandler (the MVP flow),
│       │                       EnterKeyListener, pending-module guard.
│       └── formatters/          Pure functions: state/session/event -> text.
│
├── application/           Use-case orchestration. Depends only on domain.
│   ├── commands/          Intent payloads (imperative names, NAM-007).
│   ├── queries/            Read-only request payloads.
│   ├── services/           Application Controller port (single entry
│   │                       point the CLI is allowed to call, ARQ-002).
│   └── ports/              Protocols each infrastructure adapter must
│                           fulfill: BrowserManagerPort, SessionManagerPort,
│                           NavigationRecorderPort, ElementRecorderPort,
│                           SelectorAnalyzerPort, ScreenshotEnginePort,
│                           ExportEnginePort, LogEnginePort,
│                           ConfigurationProviderPort, EventPublisherPort.
│
├── domain/                 Entities, value objects, enums, events,
│                           exceptions. No dependency on Playwright,
│                           Typer, the file system or logging
│                           libraries (ARQ-001).
│   ├── entities/            Session, Page, Frame, Element,
│   │                        ElementSelectors, Screenshot, NavigationEdge.
│   ├── value_objects/       Identifiers (SessionId, PageId, ...),
│   │                        NormalizedUrl, Resolution, Viewport,
│   │                        SelectorCandidate.
│   ├── enums/               SessionStatus, NavigationType, RelationType,
│   │                        ElementSemanticType, SelectorStrategyType,
│   │                        ScreenshotType, LogLevel,
│   │                        SensitivityClassification.
│   ├── events/               One DomainEvent subtype per module event
│   │                        listed in the Module Specifications
│   │                        ("Eventos Publicados" sections).
│   └── exceptions/           KnowledgeBuilderError and one subclass per
│                            failure mode documented per module.
│
├── infrastructure/          Concrete adapters (Playwright, file system,
│                           logging, configuration loading). Only this
│                           layer may import third-party browser-
│                           automation/logging libraries.
│   └── browser/              PlaywrightBrowserManager (ADR 0004) —
│                            implemented. storage/, logging/,
│                            configuration/ remain reserved.
│
├── modules/                 One subpackage per component from SAD
│                           section 5 / Module Specifications Chapters
│                           3-10 (session, navigation, elements,
│                           selectors, screenshots, export). Each will
│                           hold the concrete class that fulfills the
│                           matching port in application/ports.
│
├── shared/                  Dependency-free building blocks usable from
│                           any layer.
│   └── dtos/                 Pydantic v2 models mirroring the exported
│                            JSON artifacts (session.json,
│                            navigation.json, pages/*.json,
│                            selectors.json, manifest.json,
│                            screenshots metadata, statistics.json) and
│                            the AppConfig schema.
│
└── bootstrap.py             Composition root. The only file authorized
                            to choose concrete implementations for the
                            ports above (AI Coding Standards, section 10).
```

## Dependency rules (enforced by review, not yet by tooling)

```
presentation   -> application -> domain
infrastructure -> application/domain (ports)
modules/*      -> application/ports, domain
shared         -> (nothing else in src/snkb)
```

Forbidden: `domain -> infrastructure`, `domain -> presentation`,
`application -> infrastructure`, `application -> presentation`.

## Why ports live in `application`, not `domain`

Protocols such as `BrowserManagerPort` describe behaviour the
*application* layer needs from the outside world; they are not domain
concepts themselves. Keeping them in `application/ports` lets
`infrastructure` and `modules` depend on `application` without the
domain layer ever knowing an adapter exists.

## Why `AppConfig` lives in `shared`, not `infrastructure`

`ConfigurationProviderPort` (an application-layer port) returns an
`AppConfig`. If `AppConfig` lived in `infrastructure`, the application
layer would have to import infrastructure to type its own port — a
forbidden dependency. Placing boundary/config schemas in `shared`
keeps both `application` and `infrastructure` able to import it.
