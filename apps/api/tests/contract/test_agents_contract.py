"""T024 — the console routes of 003 (consent, agents, rollback requests) answer exactly what
contracts/openapi.yaml promises, errors included."""

import httpx
import pytest

from pono_api.config import Settings
from tests.conftest import FakeIdentity, requires_database
from tests.contract.test_projects_contract import UNKNOWN, conforms
from tests.fakes import World
from tests.integration.agent_setup import ask_access, connect, register, settings  # noqa: F401
from tests.integration.release_setup import lectio
from tests.integration.test_agent_tools import _two_deployments

pytestmark = [pytest.mark.contract, requires_database]


async def test_agent_surface_matches_the_contract(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await lectio(client, identity, world)
    _two_deployments(world)
    await client.post(f"/api/v1/projects/{project_id}/refresh")

    handle = await ask_access(await register(client, "Claude"))
    consent = "/oauth/consent/{decision}"
    conforms(
        await client.get("/api/v1/oauth/consent", params={"request": handle}), "/oauth/consent"
    )
    conforms(
        await client.get("/api/v1/oauth/consent", params={"request": "x" * 32}), "/oauth/consent"
    )
    conforms(
        await client.post(
            "/api/v1/oauth/consent/approve", json={"request": handle, "access": "all"}
        ),
        consent,
    )
    conforms(
        await client.post(
            "/api/v1/oauth/consent/approve", json={"request": handle, "access": "read"}
        ),
        consent,
    )
    conforms(await client.post("/api/v1/oauth/consent/deny", json={"request": handle}), consent)

    agent = await connect(client, name="Codex")
    conforms(await client.get("/api/v1/agents"), "/agents")
    asked = await agent.tool("request_rollback", project_id=project_id)
    conforms(await client.get(f"/api/v1/projects/{project_id}"), "/projects/{projectId}")

    decision = "/projects/{projectId}/rollback-requests/{requestId}/{decision}"
    base = f"/api/v1/projects/{project_id}/rollback-requests"
    conforms(await client.post(f"{base}/{UNKNOWN}/dismiss"), decision)
    conforms(await client.post(f"{base}/{asked['id']}/confirm"), decision)
    conforms(await client.post(f"{base}/{asked['id']}/dismiss"), decision)

    grant = (await client.get("/api/v1/agents")).json()[0]["id"]
    conforms(await client.delete(f"/api/v1/agents/{grant}"), "/agents/{grantId}")
    conforms(await client.delete(f"/api/v1/agents/{grant}"), "/agents/{grantId}")
