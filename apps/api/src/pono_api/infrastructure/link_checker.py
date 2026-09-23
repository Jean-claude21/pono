"""Link checker (FR-020): a link is down only after two attempts of 10 seconds each.

The first slow attempt alone never condemns a link: it absorbs the wake-up of a sleeping service.
Each attempt tries HEAD, then GET when the server refuses HEAD.
"""

import httpx

from pono_api.domain.projects import LinkStatus

TIMEOUT_SECONDS = 10.0
ATTEMPTS = 2
HEAD_REFUSED = {403, 405, 501}


class HttpLinkChecker:
    def __init__(
        self,
        *,
        timeout: float = TIMEOUT_SECONDS,
        attempts: int = ATTEMPTS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout
        self._attempts = attempts
        self._transport = transport

    async def check(self, url: str) -> LinkStatus:
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": "Pono link checker"},
        ) as client:
            for _ in range(self._attempts):
                if await self._attempt(client, url):
                    return LinkStatus.UP
        return LinkStatus.DOWN

    @staticmethod
    async def _attempt(client: httpx.AsyncClient, url: str) -> bool:
        try:
            response = await client.head(url)
            if response.status_code in HEAD_REFUSED:
                response = await client.get(url)
        except httpx.HTTPError:
            return False
        # Any answer below 500 means the service is up; a 5xx is a failed attempt.
        return response.status_code < 500


__all__ = ["ATTEMPTS", "TIMEOUT_SECONDS", "HttpLinkChecker"]
