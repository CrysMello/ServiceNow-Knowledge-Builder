"""Testes do ``OsFolderOpener`` (ADR 0014).

Nunca abre uma janela real do explorador de arquivos durante a suíte:
substitui ``os.startfile``/``subprocess.run`` por duplos, e simula cada
``sys.platform`` via ``monkeypatch`` em vez de depender do SO onde os
testes rodam.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from snkb.infrastructure.storage.folder_opener import OsFolderOpener


def test_open_uses_startfile_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(os, "startfile", lambda path: calls.append(Path(path)), raising=False)

    OsFolderOpener().open(tmp_path)

    assert calls == [tmp_path]


def test_open_uses_open_command_on_macos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(
        subprocess, "run", lambda args, check=False: calls.append(args)  # type: ignore[misc]
    )

    OsFolderOpener().open(tmp_path)

    assert calls == [["open", str(tmp_path)]]


def test_open_uses_xdg_open_on_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(
        subprocess, "run", lambda args, check=False: calls.append(args)  # type: ignore[misc]
    )

    OsFolderOpener().open(tmp_path)

    assert calls == [["xdg-open", str(tmp_path)]]
