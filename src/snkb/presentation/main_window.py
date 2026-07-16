"""UI Manager concreto, em CustomTkinter (Module Specifications, Capítulo 2).

Depende apenas de ``ApplicationControllerPort`` (ARQ-002) e dos
auxiliares livres de interface gráfica deste pacote (``UiStateMachine``,
``StatusAggregator``, ``UiEventQueue``). Nunca importa Playwright, não
interpreta seletores, não gera JSON e não grava arquivos (2.4,
"Responsabilidades Proibidas").

O botão "Sobre" é a única interação puramente local: abre um diálogo
informativo sem despachar nenhum comando, pois não faz parte do
catálogo de comandos/eventos documentado (2.6, 2.12).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from snkb import __version__
from snkb.application.commands.commands import (
    CaptureManualScreenshot,
    ExitApplication,
    OpenConfiguration,
    OpenExportFolder,
    ShowReport,
    StartCapture,
    StopCapture,
)
from snkb.domain.events.base import DomainEvent
from snkb.domain.events.session_events import SessionStarted
from snkb.presentation.state import UiState
from snkb.presentation.state_machine import UiStateMachine
from snkb.presentation.status_aggregator import StatusAggregator
from snkb.presentation.ui_event_queue import UiEventQueue
from snkb.presentation.view_models import SessionPanelViewModel, StatusPanelViewModel

if TYPE_CHECKING:
    from snkb.application.services.application_controller_port import (
        ApplicationControllerPort,
    )

# RNF: a atualização dos contadores deve ocorrer em menos de 100 ms (2.15).
_POLL_INTERVAL_MS = 100

_SESSION_FIELD_CAPTIONS: dict[str, str] = {
    "session_id": "Session ID",
    "started_at": "Data/Hora",
    "user": "Usuário",
    "instance": "Instância",
    "language": "Idioma",
    "resolution": "Resolução",
    "browser": "Navegador",
}

_COUNTER_CAPTIONS: tuple[tuple[str, str], ...] = (
    ("elapsed", "Tempo decorrido"),
    ("page_count", "Páginas"),
    ("element_count", "Elementos"),
    ("screenshot_count", "Screenshots"),
    ("log_count", "Logs"),
    ("error_count", "Erros"),
)

# Mensagens obrigatórias da interface (SRS, seção 11.1).
_SECURITY_FOOTER_TEXT = "Nenhuma credencial foi armazenada."

# UiState.FINISHED não aparece aqui: sua mensagem depende de
# ``error_count`` e é resolvida separadamente em ``_status_message``.
_STATUS_MESSAGES: dict[UiState, str] = {
    UiState.IDLE: "Ocioso.",
    UiState.STARTING: "Iniciando o navegador.",
    UiState.WAITING_LOGIN: "Aguardando autenticação Microsoft. Conclua o login no navegador.",
    UiState.RECORDING: "Gravação iniciada. Navegue normalmente no ServiceNow.",
    UiState.EXPORTING: "Finalizando e validando a Knowledge Base.",
    UiState.ERROR: "Ocorreu um erro. Consulte os logs.",
    UiState.CANCELLED: "Login cancelado.",
    UiState.INTERRUPTED: "Sessão interrompida.",
}


class CustomTkinterUserInterface:
    """Implementação de ``UserInterfacePort`` usando CustomTkinter."""

    def __init__(self, controller: ApplicationControllerPort, instance_url: str) -> None:
        self._controller = controller
        self._instance_url = instance_url

        self._state_machine = UiStateMachine()
        self._status_aggregator = StatusAggregator()
        self._event_queue = UiEventQueue()
        self._session = SessionPanelViewModel()
        self._status = StatusPanelViewModel()
        self._recording_started_at: datetime | None = None

        self._window = ctk.CTk()
        self._window.title("ServiceNow Knowledge Builder")
        self._window.protocol("WM_DELETE_WINDOW", self._on_close_request)

        self._build_top_bar()
        self._build_session_panel()
        self._build_control_panel()
        self._build_status_panel()
        self._build_events_panel()
        self._build_logs_panel()
        self._build_security_footer()

        self._render()
        self._schedule_poll()

    # ------------------------------------------------------------------
    # UserInterfacePort
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Inicia o loop principal da interface (bloqueante)."""
        self._window.mainloop()

    def shutdown(self) -> None:
        """Encerra a janela e libera seus recursos."""
        self._window.destroy()

    def handle_domain_event(self, event: DomainEvent) -> None:
        """Ponto de entrada thread-safe para eventos publicados fora da
        thread da interface (ASY-006). Nunca toca em widgets diretamente."""
        self._event_queue.submit(event)

    # ------------------------------------------------------------------
    # Construção dos widgets (2.9, "Componentes da Interface")
    # ------------------------------------------------------------------

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self._window)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(
            bar, text="ServiceNow Knowledge Builder", font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=8)
        ctk.CTkLabel(bar, text=f"v{__version__}").pack(side="left", padx=8)
        self._status_label = ctk.CTkLabel(bar, text="")
        self._status_label.pack(side="right", padx=8)

    def _build_session_panel(self) -> None:
        panel = ctk.CTkFrame(self._window)
        panel.pack(fill="x", padx=8, pady=4)
        self._session_labels: dict[str, ctk.CTkLabel] = {}
        for field_name, caption in _SESSION_FIELD_CAPTIONS.items():
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            ctk.CTkLabel(row, text=f"{caption}:", width=110, anchor="w").pack(side="left")
            value_label = ctk.CTkLabel(row, text="—", anchor="w")
            value_label.pack(side="left", fill="x", expand=True)
            self._session_labels[field_name] = value_label

    def _build_control_panel(self) -> None:
        panel = ctk.CTkFrame(self._window)
        panel.pack(fill="x", padx=8, pady=4)
        self._start_button = ctk.CTkButton(panel, text="Iniciar", command=self._on_start_clicked)
        self._start_button.pack(side="left", padx=4, pady=4)
        self._stop_button = ctk.CTkButton(panel, text="Parar", command=self._on_stop_clicked)
        self._stop_button.pack(side="left", padx=4, pady=4)
        ctk.CTkButton(panel, text="Screenshot", command=self._on_screenshot_clicked).pack(
            side="left", padx=4, pady=4
        )
        ctk.CTkButton(panel, text="Configurações", command=self._on_settings_clicked).pack(
            side="left", padx=4, pady=4
        )
        ctk.CTkButton(panel, text="Relatório", command=self._on_report_clicked).pack(
            side="left", padx=4, pady=4
        )
        ctk.CTkButton(panel, text="Abrir Pasta", command=self._on_open_folder_clicked).pack(
            side="left", padx=4, pady=4
        )
        ctk.CTkButton(panel, text="Sobre", command=self._on_about_clicked).pack(
            side="left", padx=4, pady=4
        )

    def _build_status_panel(self) -> None:
        panel = ctk.CTkFrame(self._window)
        panel.pack(fill="x", padx=8, pady=4)
        self._counter_labels: dict[str, ctk.CTkLabel] = {}
        for key, caption in _COUNTER_CAPTIONS:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(side="left", padx=8)
            ctk.CTkLabel(row, text=f"{caption}:").pack(side="left")
            value_label = ctk.CTkLabel(row, text="0")
            value_label.pack(side="left", padx=(4, 0))
            self._counter_labels[key] = value_label

    def _build_events_panel(self) -> None:
        panel = ctk.CTkFrame(self._window)
        panel.pack(fill="both", expand=True, padx=8, pady=4)
        ctk.CTkLabel(panel, text="Eventos", anchor="w").pack(fill="x")
        self._events_box = ctk.CTkTextbox(panel, height=120, state="disabled")
        self._events_box.pack(fill="both", expand=True)

    def _build_logs_panel(self) -> None:
        panel = ctk.CTkFrame(self._window)
        panel.pack(fill="both", expand=True, padx=8, pady=4)
        ctk.CTkLabel(panel, text="Logs", anchor="w").pack(fill="x")
        self._logs_box = ctk.CTkTextbox(panel, height=120, state="disabled")
        self._logs_box.pack(fill="both", expand=True)

    def _build_security_footer(self) -> None:
        # Mensagem obrigatória (SRS 11.1); sempre visível, nunca mostra
        # senha, token, cookie, código MFA ou access/refresh token (2.16).
        ctk.CTkLabel(self._window, text=_SECURITY_FOOTER_TEXT, text_color="gray60").pack(
            side="bottom", pady=(0, 6)
        )

    # ------------------------------------------------------------------
    # Despacho de comandos (2.6, 2.12) — nunca toca em Playwright/ServiceNow
    # ------------------------------------------------------------------

    def _on_start_clicked(self) -> None:
        if not self._state_machine.can_start_capture():
            return
        self._state_machine.state = UiState.STARTING
        self._render()
        self._controller.dispatch(StartCapture(instance_url=self._instance_url))

    def _on_stop_clicked(self) -> None:
        if not self._state_machine.can_stop_capture() or self._session.session_id is None:
            return
        self._controller.dispatch(StopCapture(session_id=self._session.session_id))

    def _on_screenshot_clicked(self) -> None:
        if self._session.session_id is None:
            return
        self._controller.dispatch(CaptureManualScreenshot(session_id=self._session.session_id))

    def _on_settings_clicked(self) -> None:
        self._controller.dispatch(OpenConfiguration())

    def _on_report_clicked(self) -> None:
        if self._session.session_id is None:
            return
        self._controller.dispatch(ShowReport(session_id=self._session.session_id))

    def _on_open_folder_clicked(self) -> None:
        if self._session.session_id is None:
            return
        self._controller.dispatch(OpenExportFolder(session_id=self._session.session_id))

    def _on_about_clicked(self) -> None:
        about = ctk.CTkToplevel(self._window)
        about.title("Sobre")
        ctk.CTkLabel(
            about,
            text=(
                f"ServiceNow Knowledge Builder v{__version__}\n\n"
                "Observa e mapeia sessões do ServiceNow sem automatizar\n"
                "ações de negócio nem a autenticação Microsoft."
            ),
            justify="left",
        ).pack(padx=16, pady=16)

    def _on_close_request(self) -> None:
        self._controller.dispatch(ExitApplication())
        self.shutdown()

    # ------------------------------------------------------------------
    # Consumo de eventos (2.13) e renderização
    # ------------------------------------------------------------------

    def _schedule_poll(self) -> None:
        self._window.after(_POLL_INTERVAL_MS, self._poll_events)

    def _poll_events(self) -> None:
        for event in self._event_queue.drain():
            self._consume_event(event)
        self._update_elapsed_time()
        self._render()
        self._schedule_poll()

    def _consume_event(self, event: DomainEvent) -> None:
        if isinstance(event, SessionStarted):
            self._session.session_id = event.session_id
            self._recording_started_at = datetime.now(UTC)
        self._state_machine.apply(event)
        self._status_aggregator.apply(self._status, event)
        self._append_event_line(event)

    def _append_event_line(self, event: DomainEvent) -> None:
        # Apenas o nome da classe do evento é exibido — nunca seus
        # campos — para nunca vazar um dado sensível que um produtor
        # tenha colocado em um campo livre como `reason` (2.16).
        line = f"{event.occurred_at:%H:%M:%S} — {type(event).__name__}\n"
        self._events_box.configure(state="normal")
        self._events_box.insert("end", line)
        self._events_box.configure(state="disabled")
        self._events_box.see("end")

    def _update_elapsed_time(self) -> None:
        if self._recording_started_at is None:
            self._status.elapsed_seconds = 0.0
            return
        self._status.elapsed_seconds = (
            datetime.now(UTC) - self._recording_started_at
        ).total_seconds()

    def _status_message(self) -> str:
        # Mensagens obrigatórias da interface (SRS 11.1), quando aplicável.
        state = self._state_machine.state
        if state == UiState.FINISHED:
            if self._status.error_count > 0:
                return "Sessão concluída com avisos. Consulte o relatório."
            return "Sessão concluída."
        return _STATUS_MESSAGES.get(state, state.value)

    def _render(self) -> None:
        self._status.status = self._state_machine.state
        self._status_label.configure(text=self._status_message())

        self._session_labels["session_id"].configure(
            text=str(self._session.session_id) if self._session.session_id else "—"
        )
        self._session_labels["started_at"].configure(
            text=(
                self._recording_started_at.strftime("%Y-%m-%d %H:%M:%S")
                if self._recording_started_at
                else "—"
            )
        )
        for field_name in ("user", "instance", "language", "resolution", "browser"):
            value = getattr(self._session, field_name)
            self._session_labels[field_name].configure(text=value if value else "—")

        self._counter_labels["elapsed"].configure(text=f"{self._status.elapsed_seconds:.0f}s")
        self._counter_labels["page_count"].configure(text=str(self._status.page_count))
        self._counter_labels["element_count"].configure(text=str(self._status.element_count))
        self._counter_labels["screenshot_count"].configure(text=str(self._status.screenshot_count))
        self._counter_labels["log_count"].configure(text=str(self._status.log_count))
        self._counter_labels["error_count"].configure(text=str(self._status.error_count))

        can_start = self._state_machine.can_start_capture()
        self._start_button.configure(state="normal" if can_start else "disabled")
        self._stop_button.configure(state="disabled" if can_start else "normal")
