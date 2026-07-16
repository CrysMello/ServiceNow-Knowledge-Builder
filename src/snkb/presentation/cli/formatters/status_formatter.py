"""Formata o estado atual da gravação em mensagens de terminal.

Inclui as mensagens obrigatórias da interface (SRS, seção 11.1), que
continuam válidas independentemente do front-end ser gráfico ou CLI.
"""

from __future__ import annotations

from snkb.presentation.cli.state import RecordingState

# RecordingState.FINISHED não aparece aqui: sua mensagem depende de
# quantos erros ocorreram e é resolvida separadamente em
# ``format_status_message``.
_STATUS_MESSAGES: dict[RecordingState, str] = {
    RecordingState.IDLE: "Ocioso.",
    RecordingState.STARTING: "Iniciando o navegador.",
    RecordingState.WAITING_LOGIN: (
        "Aguardando autenticação Microsoft. Conclua o login no navegador."
    ),
    RecordingState.RECORDING: "Gravação iniciada. Navegue normalmente no ServiceNow.",
    RecordingState.EXPORTING: "Finalizando e validando a Knowledge Base.",
    RecordingState.ERROR: "Ocorreu um erro. Consulte os logs.",
    RecordingState.CANCELLED: "Login cancelado.",
    RecordingState.INTERRUPTED: "Sessão interrompida.",
}

# Mensagem de segurança obrigatória (SRS 11.1), exibida ao final de
# toda sessão para deixar explícito o que nunca foi persistido.
SECURITY_FOOTER_TEXT = "Nenhuma credencial foi armazenada."


def format_status_message(state: RecordingState, error_count: int) -> str:
    """Mensagem textual correspondente ao estado atual da gravação."""
    if state == RecordingState.FINISHED:
        if error_count > 0:
            return "Sessão concluída com avisos. Consulte o relatório."
        return "Sessão concluída."
    return _STATUS_MESSAGES.get(state, state.value)
