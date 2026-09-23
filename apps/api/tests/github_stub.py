"""A scripted GitHub API for adapter tests, recording every request it receives."""

import json
from collections.abc import Callable
from functools import cache

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr

from pono_api.infrastructure.providers.github import GitHubCodeHost

Route = Callable[[httpx.Request], httpx.Response]


@cache
def private_key() -> SecretStr:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return SecretStr(pem.decode())


class GitHubStub:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.routes: dict[tuple[str, str], Route] = {
            ("POST", "/app/installations/inst-1/access_tokens"): lambda _: httpx.Response(
                201, json={"token": "installation-token"}
            ),
        }

    def on(self, method: str, path: str, status: int = 200, body: object = None) -> None:
        self.routes[(method, path)] = lambda _: httpx.Response(
            status, content=json.dumps(body).encode() if body is not None else b""
        )

    def on_text(self, method: str, path: str, text: str) -> None:
        self.routes[(method, path)] = lambda _: httpx.Response(200, text=text)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.raw_path.decode()
        route = self.routes.get((request.method, path))
        return route(request) if route else httpx.Response(404, json={"message": "Not Found"})

    def writes(self) -> list[httpx.Request]:
        return [
            request
            for request in self.requests
            if request.method != "GET" and "/access_tokens" not in request.url.path
        ]

    def adapter(self) -> GitHubCodeHost:
        return GitHubCodeHost(
            app_id="42",
            private_key=private_key(),
            api_url="https://api.github.test",
            transport=httpx.MockTransport(self.handle),
        )


__all__ = ["GitHubStub", "private_key"]
