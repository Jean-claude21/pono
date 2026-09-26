"""An agent client for tests: registers, asks for access, gets the person's consent, calls tools.

It speaks the same protocol a real agent does (OAuth 2.1 with PKCE, then MCP over Streamable HTTP),
against the application in memory.
"""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from pono_api.config import Settings
from tests.conftest import APP_URL

PUBLIC = "http://localhost:3000"
REDIRECT = "http://localhost:9999/callback"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
}


@pytest.fixture
def settings() -> Settings:
    """Agents need an issuer the standard accepts (HTTPS, or loopback here) and the cipher key."""

    return Settings(
        environment="test",
        database_app_url=SecretStr(APP_URL) if APP_URL else None,
        public_url=PUBLIC,
        allowed_logins=frozenset({"alice", "bob"}),
        encryption_key=SecretStr(Fernet.generate_key().decode()),
    )


@dataclass
class Agent:
    client: httpx.AsyncClient
    client_id: str
    access_token: str = ""
    refresh_token: str = ""
    verifier: str = ""
    calls: int = 0

    async def call(self, method: str, params: dict[str, object] | None = None) -> httpx.Response:
        self.calls += 1
        return await self.client.post(
            "/mcp",
            headers={**MCP_HEADERS, "Authorization": f"Bearer {self.access_token}"},
            json={"jsonrpc": "2.0", "id": self.calls, "method": method, "params": params or {}},
        )

    async def tool(self, name: str, **arguments: object) -> dict[str, object]:
        """The tool's structured result, or `{"error": code}` when it refused."""

        response = await self.call("tools/call", {"name": name, "arguments": arguments})
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        if result.get("isError"):
            # The SDK prefixes the message ("Error executing tool …: "); the code is the JSON part.
            text = result["content"][0]["text"]
            return {"error": json.loads(text[text.index("{") :])["code"]}
        return dict(result["structuredContent"])

    async def tools(self) -> dict[str, dict[str, object]]:
        response = await self.call("tools/list")
        assert response.status_code == 200, response.text
        return {tool["name"]: tool for tool in response.json()["result"]["tools"]}


def _challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


async def register(client: httpx.AsyncClient, name: str = "Test agent") -> Agent:
    response = await client.post(
        "/register",
        json={
            "client_name": name,
            "redirect_uris": [REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": "pono:read pono:act",
        },
    )
    assert response.status_code == 201, response.text
    return Agent(client, response.json()["client_id"])


async def ask_access(agent: Agent) -> str:
    """Start the authorization; returns the consent handle the console receives."""

    agent.verifier = secrets.token_urlsafe(48)
    response = await agent.client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": agent.client_id,
            "redirect_uri": REDIRECT,
            "code_challenge": _challenge(agent.verifier),
            "code_challenge_method": "S256",
            "state": "state-1",
            "scope": "pono:read pono:act",
            "resource": f"{PUBLIC}/mcp",
        },
    )
    assert response.status_code == 302, response.text
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == f"{PUBLIC}/oauth/consent"
    return parse_qs(location.query)["request"][0]


async def consent(client: httpx.AsyncClient, handle: str, access: str = "act") -> httpx.Response:
    return await client.post(
        "/api/v1/oauth/consent/approve", json={"request": handle, "access": access}
    )


async def exchange(agent: Agent, redirect_url: str) -> httpx.Response:
    query = parse_qs(urlsplit(redirect_url).query)
    assert query["state"] == ["state-1"]
    response = await agent.client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": REDIRECT,
            "client_id": agent.client_id,
            "code_verifier": agent.verifier,
            "resource": f"{PUBLIC}/mcp",
        },
    )
    if response.status_code == 200:
        agent.access_token = response.json()["access_token"]
        agent.refresh_token = response.json()["refresh_token"]
    return response


async def connect(
    client: httpx.AsyncClient, access: str = "act", name: str = "Test agent"
) -> Agent:
    """The whole path, with a signed-in person consenting in the console."""

    agent = await register(client, name)
    handle = await ask_access(agent)
    decided = await consent(client, handle, access)
    assert decided.status_code == 200, decided.text
    exchanged = await exchange(agent, decided.json()["redirectUrl"])
    assert exchanged.status_code == 200, exchanged.text
    return agent


__all__ = [
    "MCP_HEADERS",
    "PUBLIC",
    "REDIRECT",
    "Agent",
    "ask_access",
    "connect",
    "consent",
    "exchange",
    "register",
    "settings",
]
