"""T030 — the runtime routes of 004 answer exactly what contracts/openapi.yaml promises, errors
included."""

import httpx
import pytest

from pono_api.config import Settings
from tests.conftest import FakeIdentity, requires_database
from tests.contract.test_projects_contract import UNKNOWN, conforms
from tests.fakes import World
from tests.integration.runtime_setup import ready_runtime, runtime_project

pytestmark = [pytest.mark.contract, requires_database]

RUNTIME = "/projects/{projectId}/runtime"


async def test_runtime_surface_matches_the_contract(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    base = f"/api/v1/projects/{project_id}/runtime"
    world.gate.statuses.clear()

    conforms(await client.get(base), RUNTIME)
    conforms(await client.get(f"/api/v1/projects/{UNKNOWN}/runtime"), RUNTIME)
    conforms(await client.post(base), RUNTIME)
    files = f"{RUNTIME}/files"
    conforms(await client.put(f"{base}/files", json={"path": "a.ts", "content": "x"}), files)
    conforms(await client.put(f"{base}/files", json={"path": ".env", "content": "x"}), files)
    conforms(await client.delete(f"{base}/files", params={"path": "a.ts"}), files)
    conforms(await client.post(f"{base}/save"), f"{RUNTIME}/save")
    conforms(await client.get(f"{base}/errors"), f"{RUNTIME}/errors")
    conforms(await client.post(f"{base}/ticket", json={"return": "/"}), f"{RUNTIME}/ticket")
    world.gate.unreachable.add("https://runtime-1.test")
    conforms(await client.put(f"{base}/files", json={"path": "b.ts", "content": "x"}), files)
    conforms(await client.delete(base), RUNTIME)
    conforms(await client.post(f"{base}/ticket", json={}), f"{RUNTIME}/ticket")


async def test_refusals_match_the_contract(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
) -> None:
    project_id = await runtime_project(client, identity, world)
    del world.code_host.files[("alice/lectio-reads", "package.json")]
    base = f"/api/v1/projects/{project_id}/runtime"

    conforms(await client.post(base), RUNTIME)
    conforms(await client.get(base), RUNTIME)
    conforms(await client.get(f"{base}/errors"), f"{RUNTIME}/errors")
