"""The composition root must fail loudly, not silently, until modules
exist (PR-007: "Falhar de forma controlada e produzir diagnóstico útil")."""

from __future__ import annotations

import pytest

from snkb import bootstrap


def test_create_application_raises_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        bootstrap.create_application()
