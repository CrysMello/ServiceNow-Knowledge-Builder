# JSON Schemas

Structural (`$schema` draft 2020-12) definitions for every artifact the
Export Engine will write, mirroring the Pydantic models in
`src/snkb/shared/dtos/`. They exist independently of the Python models
so that external consumers (e.g. the future QA ServiceNow Assistant)
can validate a Knowledge Base without depending on this codebase
(RNF-016: "Leitores devem rejeitar schema incompatível com mensagem
clara").

Keep `schema_version` in `*.schema.json` in sync with the
`schema_version` field emitted by the matching Pydantic model. A
breaking change increments the major version (RF-040).
