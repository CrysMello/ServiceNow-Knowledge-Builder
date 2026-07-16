"""Confirma que nenhuma dependência de GUI permanece declarada no
projeto após a adequação para CLI (ADR 0003)."""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_does_not_declare_customtkinter() -> None:
    content = (_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "customtkinter" not in content.lower()


def test_requirements_txt_does_not_declare_customtkinter() -> None:
    content = (_PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "customtkinter" not in content.lower()


def test_customtkinter_is_not_importable_from_the_package() -> None:
    import ast

    for path in (_PROJECT_ROOT / "src" / "snkb").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module else []
            else:
                continue
            assert not any(
                name and name.startswith("customtkinter") for name in names
            ), f"{path} ainda importa customtkinter"
