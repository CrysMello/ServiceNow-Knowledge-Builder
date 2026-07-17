"""Testes do ``LoginDetector`` — a regra "pelo menos dois sinais
verdadeiros" (RF-004), sem Playwright real."""

from __future__ import annotations

from snkb.infrastructure.browser.login_detector import LoginDetector
from snkb.shared.dtos.app_config import LoginDetectionPolicyModel

_INSTANCE_URL = "https://empresa.service-now.com"


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    async def count(self) -> int:
        return self._count


class _FakePage:
    def __init__(
        self,
        url: str,
        title: str = "",
        closed: bool = False,
        marker_count: int = 0,
    ) -> None:
        self.url = url
        self._title = title
        self._closed = closed
        self._marker_count = marker_count

    def is_closed(self) -> bool:
        return self._closed

    async def title(self) -> str:
        return self._title

    def locator(self, _selector: str) -> _FakeLocator:
        return _FakeLocator(self._marker_count)


async def test_two_base_signals_true_on_the_instance_domain() -> None:
    detector = LoginDetector(LoginDetectionPolicyModel(), _INSTANCE_URL)
    page = _FakePage(url=f"{_INSTANCE_URL}/home")

    assert await detector.is_authenticated(page) is True


async def test_still_on_microsoft_login_page_is_not_authenticated() -> None:
    detector = LoginDetector(LoginDetectionPolicyModel(), _INSTANCE_URL)
    page = _FakePage(url="https://login.microsoftonline.com/common/oauth2/authorize")

    assert await detector.is_authenticated(page) is False


async def test_neither_instance_nor_microsoft_is_not_authenticated() -> None:
    # Ex.: uma tela intermediária de consentimento em outro domínio —
    # nem o sinal de domínio da instância nem o de "fora do login
    # Microsoft" (que aqui coincide por não ser um host MS conhecido)
    # bastam sozinhos sem o segundo sinal correspondente.
    detector = LoginDetector(
        LoginDetectionPolicyModel(expected_title_substring="ServiceNow"), _INSTANCE_URL
    )
    page = _FakePage(url="https://intermediate.example.com/consent", title="Consentimento")

    assert await detector.is_authenticated(page) is False


async def test_closed_page_is_never_authenticated() -> None:
    detector = LoginDetector(LoginDetectionPolicyModel(), _INSTANCE_URL)
    page = _FakePage(url=f"{_INSTANCE_URL}/home", closed=True)

    assert await detector.is_authenticated(page) is False


async def test_title_substring_signal_counts_when_configured() -> None:
    policy = LoginDetectionPolicyModel(expected_title_substring="Incident")
    detector = LoginDetector(policy, _INSTANCE_URL)
    # Fora do domínio da instância e fora do login MS: só 1 sinal base
    # (não-Microsoft) mais o título — 2 no total, deve autenticar.
    page = _FakePage(url="https://outro-dominio.example.com/x", title="Incident List")

    assert await detector.is_authenticated(page) is True


async def test_marker_selector_signal_counts_when_present() -> None:
    policy = LoginDetectionPolicyModel(service_now_marker_selector="#gsft_main")
    detector = LoginDetector(policy, _INSTANCE_URL)
    page = _FakePage(url="https://outro-dominio.example.com/x", marker_count=1)

    assert await detector.is_authenticated(page) is True


async def test_marker_selector_absent_does_not_count() -> None:
    policy = LoginDetectionPolicyModel(service_now_marker_selector="#gsft_main")
    detector = LoginDetector(policy, _INSTANCE_URL)
    page = _FakePage(url="https://outro-dominio.example.com/x", marker_count=0)

    assert await detector.is_authenticated(page) is False
