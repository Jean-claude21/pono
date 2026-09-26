"""T006 — agents' access stays inside its organization, and nothing reversible is stored
(003 FR-004, FR-005, SC-005)."""

import asyncpg
import httpx
import pytest

from pono_api.config import Settings
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World
from tests.integration.agent_setup import connect, register, settings  # noqa: F401
from tests.integration.release_setup import lectio
from tests.integration.test_agent_tools import _two_deployments
from tests.integration.workshop_setup import BOB
from tests.security.test_isolation import _as_app

pytestmark = [pytest.mark.security, requires_database]

SCOPED = ("agent_grants", "agent_tokens", "rollback_requests")
# Written before anyone is known: reachable only through the definer functions.
LOCKED = ("agent_clients", "agent_requests")


async def test_an_organization_never_sees_another_s_agents(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await lectio(client, identity, world)
    _two_deployments(world)
    await client.post(f"/api/v1/projects/{project_id}/refresh")
    agent = await connect(client, name="Claude")
    await agent.tool("request_rollback", project_id=project_id)
    await register(client, "Unconsented")
    alice_organization = (await client.get("/api/v1/me")).json()["organizationId"]
    (grant,) = (await client.get("/api/v1/agents")).json()

    await sign_in_as(client, identity, BOB)
    bob_organization = (await client.get("/api/v1/me")).json()["organizationId"]

    assert (await client.get("/api/v1/agents")).json() == []
    assert (await client.delete(f"/api/v1/agents/{grant['id']}")).json() == {
        "error": {"code": "agent.grant_not_found"}
    }
    for table in (*SCOPED, *LOCKED):
        assert await owner_fetch(f"SELECT 1 FROM {table} LIMIT 1"), f"{table} is empty"
    for table in SCOPED:
        assert await _as_app(bob_organization, f"SELECT * FROM {table}") == [], table
    for table in LOCKED:
        # Not even its own organization reads these: only the definer functions do.
        for organization in (alice_organization, bob_organization):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await _as_app(organization, f"SELECT * FROM {table}")
    # Alice's agent still works: Bob's attempt revoked nothing.
    assert "projects" in await agent.tool("list_projects")


async def test_only_digests_and_ciphertexts_are_stored(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    await lectio(client, identity, world)
    agent = await connect(client)

    columns = await owner_fetch(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_name IN ('agent_clients', 'agent_requests', 'agent_tokens') "
        "AND (column_name LIKE '%token%' OR column_name LIKE '%secret%' "
        "OR column_name LIKE '%code%' OR column_name LIKE '%digest%')"
    )
    rows = await owner_fetch(
        "SELECT encode(token_digest, 'hex') AS value FROM agent_tokens "
        "UNION ALL SELECT encode(request_digest, 'hex') FROM agent_requests"
    )

    assert columns, "no secret-bearing column found"
    for column in columns:
        if column["column_name"] == "code_challenge":
            continue  # PKCE: the challenge is public by design, the verifier never reaches us
        # A digest or a ciphertext is bytes; a readable secret would be text.
        assert column["data_type"] == "bytea", (column["table_name"], column["column_name"])
    stored = " ".join(row["value"] for row in rows)
    for secret in (agent.access_token, agent.refresh_token):
        assert secret not in stored
        assert secret.encode().hex() not in stored
