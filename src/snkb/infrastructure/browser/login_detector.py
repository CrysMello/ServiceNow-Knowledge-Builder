"""Detecta quando a autenticação Microsoft foi concluída e a instância
do ServiceNow foi carregada (SRS, seção 3.3; RF-004).

Avalia apenas sinais somente-leitura da página (URL, título e,
opcionalmente, a presença de um elemento marcador) — nunca preenche
formulários, nunca interage com a página e nunca automatiza o login
(RS-001, PW-008). A confirmação de estabilidade (aguardar o mesmo
resultado por alguns segundos antes de declarar sucesso) é
responsabilidade do chamador (``BrowserManager.wait_login``), não
deste detector, que apenas avalia o instante atual.
"""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

from snkb.shared.dtos.app_config import LoginDetectionPolicyModel

# RF-004: a detecção exige pelo menos dois sinais configuráveis
# verdadeiros simultaneamente, nunca um único seletor.
_MINIMUM_TRUE_SIGNALS = 2


class LocatorLike(Protocol):
    """Subconjunto de ``playwright.async_api.Locator`` usado aqui."""

    async def count(self) -> int: ...


class PageLike(Protocol):
    """Subconjunto somente-leitura de ``playwright.async_api.Page``
    usado pelo detector — permite testar sem um navegador real."""

    @property
    def url(self) -> str: ...
    def is_closed(self) -> bool: ...
    async def title(self) -> str: ...
    def locator(self, selector: str) -> LocatorLike: ...


class LoginDetector:
    """Avalia se a página observada já saiu do fluxo de login Microsoft
    e está na instância ServiceNow configurada."""

    def __init__(self, policy: LoginDetectionPolicyModel, instance_url: str) -> None:
        self._policy = policy
        self._instance_host = urlparse(instance_url).netloc.lower()

    async def is_authenticated(self, page: PageLike) -> bool:
        """``True`` se, neste instante, pelo menos dois sinais
        configurados indicam que a autenticação foi concluída."""
        if page.is_closed():
            return False

        signals = [
            self._matches_instance_domain(page.url),
            not self._is_microsoft_login_page(page.url),
        ]

        if self._policy.expected_title_substring:
            title = await page.title()
            signals.append(self._policy.expected_title_substring.lower() in title.lower())

        if self._policy.service_now_marker_selector:
            count = await page.locator(self._policy.service_now_marker_selector).count()
            signals.append(count > 0)

        return sum(1 for signal in signals if signal) >= _MINIMUM_TRUE_SIGNALS

    def _matches_instance_domain(self, url: str) -> bool:
        return urlparse(url).netloc.lower() == self._instance_host

    def _is_microsoft_login_page(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(
            host == known or host.endswith(f".{known}")
            for known in self._policy.microsoft_login_hostnames
        )
