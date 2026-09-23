"""T032 — `/connections`, `/repositories`, `/projects`, `/projects/{id}` and its refresh answer
exactly what contracts/openapi.yaml promises, errors included (FR-005)."""

import re

import httpx
import pytest

from pono_api.main import create_app
from tests.conftest import FakeIdentity, requires_database
from tests.contract.openapi_check import ContractChecker, load_contract
from tests.fakes import World
from tests.integration.workshop_setup import LECTIO, connect_everything, stage_lectio, stage_nettio

pytestmark = [pytest.mark.contract]

CHECKER = ContractChecker(load_contract())
UNKNOWN = "01980000-0000-7000-8000-000000000000"


def conforms(response: httpx.Response, path: str) -> None:
    schema = CHECKER.response_schema(path, response.request.method, response.status_code)
    if schema is None:
        assert response.content == b"", f"{path} {response.status_code} should have no body"
        return
    errors = CHECKER.errors(response.json(), schema)
    assert errors == [], f"{response.request.method} {path} {response.status_code}: {errors}"


def _shape(path: str) -> str:
    """Path parameters are compared by position, not by their spelling."""

    return re.sub(r"\{[^}]+\}", "{}", path)


def test_every_contract_operation_is_served() -> None:
    served = {_shape(path): item for path, item in create_app().openapi()["paths"].items()}
    for path, operations in load_contract()["paths"].items():
        for method in operations:
            assert method in served.get(_shape(f"/api/v1{path}"), {}), f"{method.upper()} {path}"


def test_the_checker_catches_what_it_should() -> None:
    project = CHECKER.schema("ProjectSummary")
    assert CHECKER.errors({"id": "x"}, project)
    assert CHECKER.errors([], project) == ["$: list where ['object'] expected"]
    state = CHECKER.errors(
        {"state": "sleeping"}, {"properties": {"state": project["properties"]["state"]}}
    )
    assert state == [
        "$.state: 'sleeping' not in ['healthy', 'active', 'warning', 'failing', 'idle']"
    ]
    assert CHECKER.errors("yesterday", {"type": "string", "format": "date-time"})
    assert CHECKER.errors(True, {"type": "integer"})


@requires_database
async def test_workshop_surface_matches_the_contract(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    stage_nettio(world)

    conforms(await client.get("/api/v1/connections"), "/connections")
    conforms(await client.post("/api/v1/connections/code-host"), "/connections/code-host")
    conforms(await client.get("/api/v1/repositories"), "/repositories")
    conforms(await client.get("/api/v1/projects"), "/projects")

    created = await client.post("/api/v1/projects", json={"repository": LECTIO})
    conforms(created, "/projects")
    project_id = created.json()["id"]
    conforms(await client.post("/api/v1/projects", json={"repository": LECTIO}), "/projects")
    conforms(
        await client.post("/api/v1/projects", json={"repository": "alice/secret"}), "/projects"
    )
    conforms(await client.get("/api/v1/projects"), "/projects")
    conforms(await client.get("/api/v1/projects", params={"state": "active"}), "/projects")
    conforms(await client.get(f"/api/v1/projects/{project_id}"), "/projects/{projectId}")
    conforms(await client.get(f"/api/v1/projects/{UNKNOWN}"), "/projects/{projectId}")
    conforms(
        await client.post(f"/api/v1/projects/{project_id}/refresh"),
        "/projects/{projectId}/refresh",
    )
    conforms(
        await client.post(f"/api/v1/projects/{UNKNOWN}/refresh"), "/projects/{projectId}/refresh"
    )
    conforms(await client.get("/api/v1/me"), "/me")

    duplicate = await client.post(
        "/api/v1/connections",
        json={"kind": "database", "provider": "neon", "authorization": "neon-key"},
    )
    conforms(duplicate, "/connections")
    conforms(await client.delete(f"/api/v1/connections/{UNKNOWN}"), "/connections/{connectionId}")
    connection_id = (await client.get("/api/v1/connections")).json()[-1]["id"]
    conforms(
        await client.delete(f"/api/v1/connections/{connection_id}"), "/connections/{connectionId}"
    )
