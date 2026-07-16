# Integration tests

Reserved for tests that exercise real infrastructure under control (a
real Playwright browser against a disposable page, real file writes,
real serialization) once the corresponding adapters in
`src/snkb/infrastructure/` and `src/snkb/modules/` are implemented.

Per AI Coding Standards (section 19), these tests must not reach the
internet or a real corporate ServiceNow instance by default.
