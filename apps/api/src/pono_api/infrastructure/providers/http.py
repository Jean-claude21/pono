"""Shared HTTP call for key-based provider adapters.

Each call records its action through `on_use` before leaving (FR-011, D-007), maps a refused
credential to `ProviderAuthorizationError` and any other failure to `ProviderUnavailableError`.
"""

from datetime import datetime
from typing import cast

import httpx

from pono_api.application.ports import (
    KeyUse,
    ProviderAuthorizationError,
    ProviderUnavailableError,
)

JsonObject = dict[str, object]


class KeyedClient:
    def __init__(
        self,
        base_url: str,
        authorization: str,
        on_use: KeyUse,
        *,
        provider: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._authorization = authorization
        self._on_use = on_use
        self._provider = provider
        self._transport = transport

    async def get(self, path: str, action: str, *, allow_missing: bool = False) -> object | None:
        """GET a JSON document; None when `allow_missing` and the resource does not exist."""

        return await self._call("GET", path, action, allow_missing=allow_missing)

    async def post(
        self,
        path: str,
        action: str,
        payload: JsonObject | None = None,
        *,
        allow_missing: bool = False,
    ) -> object | None:
        """POST: bringing production back (002 R-08), and the runtime's application (004)."""

        return await self._call("POST", path, action, payload, allow_missing=allow_missing)

    async def delete(self, path: str, action: str) -> object | None:
        """DELETE, for the runtime's own application and key only (004, D-019)."""

        return await self._call("DELETE", path, action, allow_missing=True)

    async def _call(
        self,
        method: str,
        path: str,
        action: str,
        payload: JsonObject | None = None,
        *,
        allow_missing: bool = False,
    ) -> object | None:
        self._on_use(action)
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=20) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers={
                        "Authorization": f"Bearer {self._authorization}",
                        "Accept": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(f"{self._provider} {action} failed") from error
        if response.status_code in {401, 403}:
            raise ProviderAuthorizationError(f"{self._provider} refused the credential")
        if response.status_code == 404 and allow_missing:
            return None
        if response.status_code >= 400:
            raise ProviderUnavailableError(
                f"{self._provider} {action} answered {response.status_code}"
            )
        if not response.content:
            return None
        try:
            return cast(object, response.json())
        except ValueError as error:
            raise ProviderUnavailableError(f"{self._provider} {action} returned no JSON") from error


def as_object(value: object) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def text(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def same_repository(url_or_name: str | None, repository: str) -> bool:
    """True when a provider's repository reference points at `owner/name`."""

    if not url_or_name:
        return False
    cleaned = url_or_name.strip().rstrip("/").removesuffix(".git").lower()
    target = repository.lower()
    return cleaned == target or cleaned.endswith(f"/{target}") or cleaned.endswith(f":{target}")


__all__ = ["KeyedClient", "as_list", "as_object", "same_repository", "text", "timestamp"]
