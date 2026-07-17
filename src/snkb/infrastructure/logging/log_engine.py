"""Implementação concreta de ``LogEnginePort`` (Module Specifications,
Capítulo 10), usando Loguru como backend de persistência.

Único módulo autorizado a gravar arquivos de log (10.1) — todo módulo
central recebe um ``LogEnginePort`` por injeção de dependência e nunca
grava logs diretamente. Único pacote autorizado a importar ``loguru``
(mesmo princípio de isolamento do PW-001 para Playwright). Ver ADR 0011
para as decisões de design.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger as _default_logger

from snkb.domain.enums.log_level import LogLevel
from snkb.domain.exceptions.log_exceptions import InvalidLogLevelError

if TYPE_CHECKING:
    from loguru import Logger

_LOGURU_LEVEL_BY_NAME: dict[str, str] = {
    LogLevel.TRACE.value: "TRACE",
    LogLevel.DEBUG.value: "DEBUG",
    LogLevel.INFO.value: "INFO",
    LogLevel.WARNING.value: "WARNING",
    LogLevel.ERROR.value: "ERROR",
    LogLevel.CRITICAL.value: "CRITICAL",
}

_LEVEL_ORDER: list[str] = [
    LogLevel.TRACE.value,
    LogLevel.DEBUG.value,
    LogLevel.INFO.value,
    LogLevel.WARNING.value,
    LogLevel.ERROR.value,
    LogLevel.CRITICAL.value,
]

_DEFAULT_RETENTION_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LoguruLogEngine:
    """Serviço de logging centralizado e estruturado, com um registro em
    memória (para ``export()``/``statistics()``) espelhado em arquivo via
    Loguru (para auditoria persistente)."""

    def __init__(
        self,
        log_directory: Path,
        log_level: str = "info",
        retention_days: int = _DEFAULT_RETENTION_DAYS,
        now: Callable[[], datetime] = _utcnow,
        logger_instance: Logger = _default_logger,
    ) -> None:
        normalized_level = log_level.lower()
        if normalized_level not in _LOGURU_LEVEL_BY_NAME:
            raise InvalidLogLevelError(
                f"Nível de log inválido: {log_level!r}. "
                f"Valores aceitos: {sorted(_LOGURU_LEVEL_BY_NAME)}."
            )

        self._now = now
        self._log_level = normalized_level
        self._entries: list[dict[str, object]] = []
        self._logger = logger_instance

        log_directory.mkdir(parents=True, exist_ok=True)
        self._logger.remove()
        self._logger.add(
            log_directory / "snkb_{time:YYYY-MM-DD}.log",
            level="TRACE",
            serialize=True,
            rotation="00:00",
            retention=f"{retention_days} days",
            enqueue=False,
        )

    # ------------------------------------------------------------------
    # LogEnginePort
    # ------------------------------------------------------------------

    def trace(self, message: str, **context: object) -> None:
        self._log(LogLevel.TRACE.value, message, context)

    def debug(self, message: str, **context: object) -> None:
        self._log(LogLevel.DEBUG.value, message, context)

    def info(self, message: str, **context: object) -> None:
        self._log(LogLevel.INFO.value, message, context)

    def warning(self, message: str, **context: object) -> None:
        self._log(LogLevel.WARNING.value, message, context)

    def error(self, message: str, **context: object) -> None:
        self._log(LogLevel.ERROR.value, message, context)

    def critical(self, message: str, **context: object) -> None:
        self._log(LogLevel.CRITICAL.value, message, context)

    def exception(self, message: str, **context: object) -> None:
        """Deve ser chamado de dentro de um bloco ``except`` — como
        ``logging.Logger.exception``, anexa o traceback corrente (nível
        ``error``)."""
        self._log(LogLevel.ERROR.value, message, context, with_traceback=True)

    def flush(self) -> None:
        self._logger.complete()

    def export(self) -> list[dict[str, object]]:
        return [dict(entry) for entry in self._entries]

    def statistics(self) -> dict[str, object]:
        by_level: dict[str, int] = {}
        for entry in self._entries:
            level = str(entry["level"])
            by_level[level] = by_level.get(level, 0) + 1
        return {
            "total_entries": len(self._entries),
            "by_level": by_level,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _is_enabled(self, level: str) -> bool:
        return _LEVEL_ORDER.index(level) >= _LEVEL_ORDER.index(self._log_level)

    def _log(
        self,
        level: str,
        message: str,
        context: dict[str, object],
        *,
        with_traceback: bool = False,
    ) -> None:
        if not self._is_enabled(level):
            return

        entry: dict[str, object] = {
            **context,
            "timestamp": self._now().isoformat(),
            "level": level,
            "message": message,
        }
        self._entries.append(entry)

        bound = self._logger.bind(**context)
        loguru_level = _LOGURU_LEVEL_BY_NAME[level]
        if with_traceback:
            bound.opt(exception=True).log(loguru_level, message)
        else:
            bound.log(loguru_level, message)
