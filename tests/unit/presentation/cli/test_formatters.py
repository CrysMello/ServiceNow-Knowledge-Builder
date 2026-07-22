"""Testes das funções puras de formatação de terminal."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from snkb.application.ports.log_reader_port import LogRecordSummary
from snkb.application.ports.session_discovery_port import SessionSummary
from snkb.domain.events.session_events import SessionFailed
from snkb.presentation.cli.formatters.config_formatter import format_config
from snkb.presentation.cli.formatters.event_formatter import format_event_line
from snkb.presentation.cli.formatters.log_formatter import format_log_records
from snkb.presentation.cli.formatters.session_formatter import format_session_info
from snkb.presentation.cli.formatters.session_summary_formatter import format_session_summary
from snkb.presentation.cli.formatters.status_formatter import (
    SECURITY_FOOTER_TEXT,
    format_status_message,
)
from snkb.presentation.cli.state import RecordingState
from snkb.presentation.cli.view_models import RecordingCounters, SessionInfo
from snkb.shared.dtos.app_config import AppConfig


def test_format_status_message_covers_waiting_login() -> None:
    message = format_status_message(RecordingState.WAITING_LOGIN, error_count=0)

    assert "Aguardando autenticação Microsoft" in message


def test_format_status_message_finished_without_errors() -> None:
    message = format_status_message(RecordingState.FINISHED, error_count=0)

    assert message == "Sessão concluída."


def test_format_status_message_finished_with_errors_mentions_warnings() -> None:
    message = format_status_message(RecordingState.FINISHED, error_count=2)

    assert "avisos" in message


def test_security_footer_text_is_the_mandatory_srs_message() -> None:
    assert SECURITY_FOOTER_TEXT == "Nenhuma credencial foi armazenada."


def test_format_session_info_uses_placeholder_for_missing_fields() -> None:
    text = format_session_info(SessionInfo(), RecordingCounters())

    assert "—" in text
    assert "Session ID" in text
    assert "Páginas: 0" in text


def test_format_session_info_shows_known_fields(fixed_session_uuid: UUID) -> None:
    info = SessionInfo(session_id=fixed_session_uuid, instance="empresa")
    counters = RecordingCounters(page_count=3)

    text = format_session_info(info, counters)

    assert str(fixed_session_uuid) in text
    assert "empresa" in text
    assert "Páginas: 3" in text


def test_format_event_line_never_leaks_event_fields(fixed_session_uuid: UUID) -> None:
    secret_reason = "vazamento-hipotetico-nao-deveria-aparecer"
    event = SessionFailed(session_id=fixed_session_uuid, reason=secret_reason)

    line = format_event_line(event)

    assert secret_reason not in line
    assert "SessionFailed" in line


def test_format_event_line_includes_a_hh_mm_ss_timestamp(fixed_session_uuid: UUID) -> None:
    event = SessionFailed(session_id=fixed_session_uuid, reason="x")

    line = format_event_line(event)

    assert re.match(r"^\d{2}:\d{2}:\d{2} — SessionFailed$", line)


def test_format_session_summary_shows_all_fields(fixed_session_uuid: UUID) -> None:
    summary = SessionSummary(
        session_id=fixed_session_uuid,
        status="completed",
        instance_url="https://empresa.service-now.com",
        export_directory=Path("exports") / str(fixed_session_uuid),
        recording_start=datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC),
        recording_end=None,
        total_pages=2,
        total_elements=5,
        total_screenshots=2,
        error_count=0,
    )

    text = format_session_summary(summary)

    assert str(fixed_session_uuid) in text
    assert "completed" in text
    assert "Páginas: 2" in text
    assert "Fim: —" in text


def test_format_config_shows_top_level_and_nested_fields() -> None:
    config = AppConfig(
        instance_url="https://empresa.service-now.com", output_directory=Path("exports")
    )

    text = format_config(config)

    assert "instance_url: https://empresa.service-now.com" in text
    assert "capture_policy:" in text
    assert "login_detection:" in text


def test_format_log_records_shows_no_records_message() -> None:
    assert "Nenhum registro" in format_log_records([])


def test_format_log_records_shows_one_line_per_record() -> None:
    records = [
        LogRecordSummary(
            timestamp=datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC),
            level="INFO",
            module="session_manager",
            message="Sessão criada.",
        )
    ]

    text = format_log_records(records)

    assert "[INFO]" in text
    assert "session_manager" in text
    assert "Sessão criada." in text
