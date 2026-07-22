"""Implementação concreta de ``ConfigurationProviderPort`` (CFG-001 a
CFG-006, ADR 0015).

Substitui o carregador mínimo que ``bootstrap._load_config()`` usava
antes deste ADR: além de validar via ``AppConfig``, converte cada erro
do Pydantic em uma mensagem que identifica o campo ofensivo (CFG-006),
em vez de propagar o traceback bruto do ``pydantic.ValidationError``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pydantic

from snkb.domain.exceptions.configuration_exceptions import (
    ConfigurationError,
    InvalidConfigurationError,
)
from snkb.shared.dtos.app_config import AppConfig


class JsonConfigurationProvider:
    """Carrega e valida ``AppConfig`` a partir do primeiro arquivo
    existente em ``candidates``.

    ``reload()`` simplesmente relê o disco — o adaptador não guarda
    estado, então "recarregar em tempo de execução" (CFG-006) é apenas
    chamar ``load()`` de novo, sem cache a invalidar.
    """

    def __init__(self, candidates: Sequence[Path]) -> None:
        self._candidates = tuple(candidates)

    def load(self) -> AppConfig:
        path = self._resolve_path()
        raw = path.read_text(encoding="utf-8")
        try:
            return AppConfig.model_validate_json(raw)
        except pydantic.ValidationError as error:
            raise InvalidConfigurationError(_format_validation_error(path, error)) from error

    def reload(self) -> AppConfig:
        return self.load()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_path(self) -> Path:
        for candidate in self._candidates:
            if candidate.is_file():
                return candidate
        raise ConfigurationError(
            "snkb: nenhum arquivo de configuração encontrado "
            f"({', '.join(str(path) for path in self._candidates)}). "
            "Copie config/default.json para config/local.json e ajuste instance_url/"
            "output_directory antes de gravar uma sessão real."
        )


def _format_validation_error(path: Path, error: pydantic.ValidationError) -> str:
    field_messages = [
        f"campo '{'.'.join(str(part) for part in item['loc'])}': {item['msg']} "
        f"(valor recebido: {item.get('input')!r})"
        for item in error.errors()
    ]
    joined = "; ".join(field_messages)
    return f"Configuração inválida em {path}: {joined}."
