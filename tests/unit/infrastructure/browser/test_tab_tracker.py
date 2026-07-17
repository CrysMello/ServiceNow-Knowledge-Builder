"""Testes do ``TabTracker`` — puros, sem Playwright real.

Usa um objeto qualquer com atributo ``url`` como substituto de
``playwright.async_api.Page``, já que o tracker só usa a página como
chave de dicionário e lê ``page.url``.
"""

from __future__ import annotations

from dataclasses import dataclass

from snkb.infrastructure.browser.tab_tracker import TabTracker


@dataclass(eq=False)  # identidade (não igualdade por valor), como o Page real do Playwright
class _FakePage:
    url: str


def test_register_assigns_a_stable_tab_id() -> None:
    tracker = TabTracker()
    page = _FakePage(url="https://empresa.service-now.com/home")

    tab_id = tracker.register(page)

    assert tracker.tab_id_for(page) == tab_id


def test_register_is_idempotent_for_the_same_page() -> None:
    tracker = TabTracker()
    page = _FakePage(url="https://empresa.service-now.com/home")

    first = tracker.register(page)
    second = tracker.register(page)

    assert first == second
    assert len(tracker.open_tabs()) == 1


def test_two_different_pages_get_different_tab_ids() -> None:
    tracker = TabTracker()
    first_page = _FakePage(url="https://empresa.service-now.com/home")
    second_page = _FakePage(url="https://empresa.service-now.com/list")

    first_id = tracker.register(first_page)
    second_id = tracker.register(second_page)

    assert first_id != second_id
    assert len(tracker.open_tabs()) == 2


def test_close_removes_page_from_open_tabs_but_keeps_the_record() -> None:
    tracker = TabTracker()
    page = _FakePage(url="https://empresa.service-now.com/home")
    tab_id = tracker.register(page)

    closed_id = tracker.close(page)

    assert closed_id == tab_id
    assert tracker.open_tabs() == []
    assert tracker.tab_id_for(page) == tab_id  # o registro em si persiste


def test_close_untracked_page_returns_none() -> None:
    tracker = TabTracker()
    page = _FakePage(url="https://empresa.service-now.com/home")

    assert tracker.close(page) is None


def test_is_tracked_reflects_registration_state() -> None:
    tracker = TabTracker()
    page = _FakePage(url="https://empresa.service-now.com/home")

    assert tracker.is_tracked(page) is False
    tracker.register(page)
    assert tracker.is_tracked(page) is True
