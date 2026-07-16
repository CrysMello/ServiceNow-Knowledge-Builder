"""Formata os dados de sessão e os contadores de gravação em um bloco de
texto de terminal (Module Specifications, Capítulo 2, seção 2.9 —
adaptado de "Painel da Sessão"/"Painel de Status" para texto simples).
"""

from __future__ import annotations

from snkb.presentation.cli.view_models import RecordingCounters, SessionInfo

_SESSION_FIELD_CAPTIONS: tuple[tuple[str, str], ...] = (
    ("session_id", "Session ID"),
    ("started_at", "Data/Hora"),
    ("user", "Usuário"),
    ("instance", "Instância"),
    ("language", "Idioma"),
    ("resolution", "Resolução"),
    ("browser", "Navegador"),
)

_COUNTER_CAPTIONS: tuple[tuple[str, str], ...] = (
    ("page_count", "Páginas"),
    ("element_count", "Elementos"),
    ("screenshot_count", "Screenshots"),
    ("log_count", "Logs"),
    ("error_count", "Erros"),
)


def format_session_info(info: SessionInfo, counters: RecordingCounters) -> str:
    """Bloco de texto multilinha com os dados da sessão e os contadores
    atuais, pronto para impressão no terminal."""
    lines: list[str] = []

    for field_name, caption in _SESSION_FIELD_CAPTIONS:
        value = getattr(info, field_name)
        if field_name == "started_at" and value is not None:
            value = value.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{caption}: {value if value else '—'}")

    lines.append(f"Tempo decorrido: {counters.elapsed_seconds:.0f}s")
    for field_name, caption in _COUNTER_CAPTIONS:
        lines.append(f"{caption}: {getattr(counters, field_name)}")

    return "\n".join(lines)
