"""T027 — the production branch is protected, and Pono says so (002 US3, FR-013 to FR-015)."""

import httpx
import pytest

from pono_api.domain.releases import ProtectionStatus
from tests.conftest import FakeIdentity, requires_database
from tests.fakes import World
from tests.integration.release_setup import journal, lectio
from tests.integration.workshop_setup import LECTIO

pytestmark = [pytest.mark.integration, requires_database]


async def test_an_unprotected_project_is_flagged_then_protected_on_a_click(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    project_id = await lectio(client, identity, world)

    detail = (await client.get(f"/api/v1/projects/{project_id}")).json()
    assert detail["protection"]["status"] == "unprotected"
    assert detail["protection"]["branch"] == "main"
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project_id, "code": "project.unprotected"} in workshop["verdicts"]

    applied = await client.post(f"/api/v1/projects/{project_id}/protection")

    assert applied.status_code == 200
    assert applied.json()["status"] == "protected"
    assert world.code_host.protected == [(LECTIO, "main")]
    assert (await journal(client, project_id))[-1] == "protection.applied"
    workshop = (await client.get("/api/v1/projects")).json()
    assert all(v["code"] != "project.unprotected" for v in workshop["verdicts"])


async def test_a_protection_removed_at_the_code_host_is_noticed(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    world.code_host.protection[LECTIO] = ProtectionStatus.PROTECTED
    project_id = await lectio(client, identity, world)
    assert (await client.get(f"/api/v1/projects/{project_id}")).json()["protection"][
        "status"
    ] == "protected"

    world.code_host.protection[LECTIO] = ProtectionStatus.UNPROTECTED
    await client.post(f"/api/v1/projects/{project_id}/refresh")

    assert (await client.get(f"/api/v1/projects/{project_id}")).json()["protection"][
        "status"
    ] == "unprotected"
    assert (await journal(client, project_id))[-1] == "protection.missing"


@pytest.mark.parametrize(
    "refusal", ["protection.unavailable_on_plan", "protection.permission_missing"]
)
async def test_a_refusal_of_the_code_host_is_said_as_it_is(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    refusal: str,
) -> None:
    project_id = await lectio(client, identity, world)
    world.code_host.protection_refusal = refusal

    refused = await client.post(f"/api/v1/projects/{project_id}/protection")

    assert refused.status_code == 422
    assert refused.json() == {"error": {"code": refusal}}
    assert world.code_host.protected == []


async def test_a_plan_without_protection_is_never_shown_as_protected(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    world.code_host.protection[LECTIO] = ProtectionStatus.UNAVAILABLE_ON_PLAN
    project_id = await lectio(client, identity, world)

    detail = (await client.get(f"/api/v1/projects/{project_id}")).json()
    workshop = (await client.get("/api/v1/projects")).json()

    assert detail["protection"]["status"] == "unavailable_on_plan"
    assert {"projectId": project_id, "code": "project.protection_unavailable"} in workshop[
        "verdicts"
    ]
    assert await journal(client, project_id) == ["protection.unavailable"]
