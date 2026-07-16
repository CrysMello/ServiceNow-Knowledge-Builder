"""Testes dos comandos publicados pelo UI Manager (Module Specifications
2.12)."""

from __future__ import annotations

from uuid import UUID

from snkb.application.commands.commands import OpenExportFolder, ShowReport


def test_open_export_folder_carries_session_id(fixed_session_uuid: UUID) -> None:
    command = OpenExportFolder(session_id=fixed_session_uuid)

    assert command.session_id == fixed_session_uuid


def test_show_report_carries_session_id(fixed_session_uuid: UUID) -> None:
    command = ShowReport(session_id=fixed_session_uuid)

    assert command.session_id == fixed_session_uuid
