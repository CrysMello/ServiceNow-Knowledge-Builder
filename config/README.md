# Configuration

`default.json` mirrors `snkb.shared.dtos.app_config.AppConfig` and its
secure-by-default values (CFG-002). It is versioned as a template.

For a real environment, copy it to `config/local.json` (already
gitignored) and set `instance_url` to the real ServiceNow instance —
never commit a real instance URL or any credential here (RS-010,
CFG-003, CFG-004: "A URL da instância será configuração, nunca
hardcoded").

The Configuration Manager adapter (`src/snkb/infrastructure/configuration/`,
not yet implemented) will be the only component that reads this file.
