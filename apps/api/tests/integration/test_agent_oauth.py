"""T010 — an agent registers alone and gets an access only after a person's consent, given in the
console (003 US1, FR-001 to FR-005, SC-005)."""

import httpx
import pytest

from pono_api.application.identity import CodeHostUser
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World
from tests.integration.agent_setup import (
    PUBLIC,
    ask_access,
    connect,
    consent,
    exchange,
    register,
    settings,  # noqa: F401  (agents need their own settings)
)
from tests.integration.workshop_setup import ALICE, connect_everything

pytestmark = [pytest.mark.integration, requires_database]


async def test_the_server_says_how_to_authorize_without_any_key(
    clean_database: None, client: httpx.AsyncClient
) -> None:
    resource = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()
    server = (await client.get("/.well-known/oauth-authorization-server")).json()
    anonymous = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert resource["resource"] == f"{PUBLIC}/mcp"
    assert resource["authorization_servers"] == [f"{PUBLIC}/"]
    # An agent reads here what it may ask for: acting too, the person deciding at consent.
    assert resource["scopes_supported"] == ["pono:read", "pono:act"]
    assert server["registration_endpoint"] == f"{PUBLIC}/register"
    assert "S256" in server["code_challenge_methods_supported"]
    assert anonymous.status_code == 401
    assert "oauth-protected-resource" in anonymous.headers["www-authenticate"]


async def test_the_full_path_from_registration_to_a_tool(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    agent = await register(client, "Claude")
    handle = await ask_access(agent)

    view = await client.get("/api/v1/oauth/consent", params={"request": handle})
    assert view.status_code == 200
    assert view.json()["clientName"] == "Claude"
    assert set(view.json()["scopes"]) == {"pono:read", "pono:act"}

    decided = await consent(client, handle, "act")
    exchanged = await exchange(agent, decided.json()["redirectUrl"])
    assert exchanged.status_code == 200
    assert exchanged.json()["scope"] == "pono:read pono:act"

    listed = await agent.tool("list_projects")
    assert listed["projects"] == []
    agents = (await client.get("/api/v1/agents")).json()
    assert [(a["clientName"], a["access"]) for a in agents] == [("Claude", "act")]

    # Nothing reversible is kept: neither the tokens, nor the code, nor the consent handle.
    stored = await owner_fetch(
        "SELECT encode(token_digest, 'hex') AS digest FROM agent_tokens "
        "UNION ALL SELECT encode(request_digest, 'hex') FROM agent_requests"
    )
    everything = " ".join(row["digest"] for row in stored)
    for secret in (agent.access_token, agent.refresh_token, handle):
        assert secret not in everything
        assert secret.encode().hex() not in everything


async def test_a_refusal_gives_the_agent_nothing(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    agent = await register(client)
    handle = await ask_access(agent)

    denied = await client.post("/api/v1/oauth/consent/deny", json={"request": handle})

    assert "error=access_denied" in denied.json()["redirectUrl"]
    again = await consent(client, handle)
    assert again.json() == {"error": {"code": "oauth.request_not_found"}}
    assert await owner_fetch("SELECT 1 FROM agent_grants") == []


async def test_a_read_only_access_cannot_act(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    agent = await connect(client, access="read")

    refused = await agent.tool("refresh_project", project_id="01980000-0000-7000-8000-000000000000")

    assert refused == {"error": "agent.scope_insufficient"}
    assert (await client.get("/api/v1/agents")).json()[0]["access"] == "read"


async def test_the_consent_needs_a_signed_in_allowed_person(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    agent = await register(client)
    handle = await ask_access(agent)

    anonymous = await client.get("/api/v1/oauth/consent", params={"request": handle})
    outsider = await sign_in_as(client, identity, CodeHostUser("9999", "mallory", None))

    assert anonymous.status_code == 401
    assert "auth.not_allowed" in outsider.headers["location"]
    await sign_in_as(client, identity, ALICE)
    assert (
        await client.get("/api/v1/oauth/consent", params={"request": handle})
    ).status_code == 200


async def test_refresh_rotates_and_revocation_cuts_at_once(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    agent = await connect(client)
    old_refresh = agent.refresh_token

    refreshed = await client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": old_refresh,
            "client_id": agent.client_id,
        },
    )
    reused = await client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": old_refresh,
            "client_id": agent.client_id,
        },
    )
    assert refreshed.status_code == 200
    assert reused.status_code == 400  # a refresh token works once
    agent.access_token = refreshed.json()["access_token"]
    assert "projects" in await agent.tool("list_projects")

    (grant,) = (await client.get("/api/v1/agents")).json()
    assert (await client.delete(f"/api/v1/agents/{grant['id']}")).status_code == 204

    cut = await agent.call("tools/list")
    assert cut.status_code == 401
    assert (await client.get("/api/v1/agents")).json() == []


async def test_a_code_works_once_and_only_with_its_verifier(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    agent = await register(client)
    handle = await ask_access(agent)
    redirect = (await consent(client, handle)).json()["redirectUrl"]

    verifier = agent.verifier
    agent.verifier = "not-the-verifier-" + "x" * 40
    assert (await exchange(agent, redirect)).status_code == 400
    agent.verifier = verifier
    assert (await exchange(agent, redirect)).status_code == 200
    assert (await exchange(agent, redirect)).status_code == 400
