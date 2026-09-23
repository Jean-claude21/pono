"""GitHub App user authorization: the sign-in half of the single Pono GitHub App (research R-03).

Only the identity is kept. The user token is used once, to read who signed in, then dropped.
"""

from typing import cast
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from pono_api.application.identity import CodeHostUser, IdentityProviderError

JsonObject = dict[str, object]


class GitHubIdentity:
    def __init__(
        self,
        client_id: str,
        client_secret: SecretStr,
        *,
        web_url: str = "https://github.com",
        api_url: str = "https://api.github.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._web_url = web_url.rstrip("/")
        self._api_url = api_url.rstrip("/")
        self._transport = transport

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {"client_id": self._client_id, "redirect_uri": redirect_uri, "state": state}
        )
        return f"{self._web_url}/login/oauth/authorize?{query}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        async with httpx.AsyncClient(transport=self._transport, timeout=10) as client:
            response = await client.post(
                f"{self._web_url}/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret.get_secret_value(),
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
        payload = cast(JsonObject, response.json()) if response.status_code == 200 else {}
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise IdentityProviderError("code host refused the authorization code")
        return token

    async def fetch_user(self, user_token: str) -> CodeHostUser:
        async with httpx.AsyncClient(transport=self._transport, timeout=10) as client:
            response = await client.get(
                f"{self._api_url}/user",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {user_token}",
                },
            )
        if response.status_code != 200:
            raise IdentityProviderError("code host did not return the signed-in user")
        payload = cast(JsonObject, response.json())
        user_id, login, email = payload.get("id"), payload.get("login"), payload.get("email")
        if not isinstance(user_id, int) or not isinstance(login, str):
            raise IdentityProviderError("code host returned an incomplete user")
        return CodeHostUser(
            user_id=str(user_id), login=login, email=email if isinstance(email, str) else None
        )


__all__ = ["GitHubIdentity"]
