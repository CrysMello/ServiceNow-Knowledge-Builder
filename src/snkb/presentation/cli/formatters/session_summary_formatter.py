"""Formata um ``SessionSummary`` (descoberta de sessão em disco, ADR
0014) em um bloco de texto de terminal, para os comandos ``snkb
status``/``snkb validate``.

Distinto de ``session_formatter.py``: aquele formata ``SessionInfo``/
``RecordingCounters``, específicos da gravação ao vivo de ``snkb
record`` (orientados a evento). Este formata o que a leitura pontual de
``session.json``/``statistics.json`` de uma sessão já encerrada
realmente tem — sem "Usuário"/"Idioma"/"Navegador", que essa leitura
não recupera hoje.
"""

from __future__ import annotations

from snkb.application.ports.session_discovery_port import SessionSummary

_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_session_summary(summary: SessionSummary) -> str:
    """Bloco de texto multilinha com os dados e contadores da sessão
    mais recente exportada em disco."""
    lines = [
        f"Session ID: {summary.session_id}",
        f"Status: {summary.status}",
        f"Instância: {summary.instance_url}",
        f"Início: {summary.recording_start.strftime(_DATETIME_FORMAT)}",
        (
            f"Fim: {summary.recording_end.strftime(_DATETIME_FORMAT)}"
            if summary.recording_end is not None
            else "Fim: —"
        ),
        f"Diretório de exportação: {summary.export_directory}",
        f"Páginas: {summary.total_pages}",
        f"Elementos: {summary.total_elements}",
        f"Screenshots: {summary.total_screenshots}",
        f"Erros: {summary.error_count}",
    ]
    return "\n".join(lines)
