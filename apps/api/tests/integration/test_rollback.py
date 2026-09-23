"""T031 — production back to the previous deployment in one confirmed gesture (002 US4)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from pono_api.application.rollback import ROLLBACK_TIMEOUT, settle_rollbacks
from pono_api.config import Settings
from pono_api.infrastructure.database.rls import Principal
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from tests.conftest import FakeIdentity, owner_fetch, requires_database
from tests.fakes import World, deployment
from tests.integration.release_setup import journal, lectio
from tests.integration.workshop_setup import NETTIO, stage_nettio

pytestmark = [pytest.mark.integration, requires_database]


def _two_commits(world: World) -> None:
    netlify = world.factory.hosting_adapters["netlify"]
    site = netlify.environments["site-lectio"]
    netlify.environments["site-lectio"] = replace(
        site,
        deployments=(
            deployment("netlify-2", commit="new0001", age=timedelta(hours=1)),
            deployment("netlify-1", commit="old0001", age=timedelta(days=2)),
        ),
        live_commit="new0001",
    )


async def _settle(settings: Settings, world: World, now: datetime | None = None) -> None:
    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    try:
        organization = (await owner_fetch("SELECT id FROM organizations"))[0]["id"]
        await settle_rollbacks(
            create_session_factory(engine),
            Principal.for_organization(organization),
            world.providers,
            now,
        )
    finally:
        await engine.dispose()


async def test_production_goes_back_and_the_outcome_is_confirmed_by_the_host(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    _two_commits(world)
    await client.post(f"/api/v1/projects/{project_id}/refresh")
    assert (await client.get(f"/api/v1/projects/{project_id}")).json()["canRollback"] is True

    requested = await client.post(f"/api/v1/projects/{project_id}/rollback")
    again = await client.post(f"/api/v1/projects/{project_id}/rollback")

    assert requested.status_code == 202
    assert (requested.json()["status"], requested.json()["toCommit"]) == ("queued", "old0001")
    assert again.json() == {"error": {"code": "rollback.in_progress"}}
    assert world.factory.hosting_adapters["netlify"].rolled_back == [("site-lectio", "netlify-1")]

    await _settle(settings, world)  # the host still serves the new commit: nothing is claimed yet
    assert (await owner_fetch("SELECT status FROM rollbacks"))[0]["status"] == "queued"

    netlify = world.factory.hosting_adapters["netlify"]
    netlify.environments["site-lectio"] = replace(
        netlify.environments["site-lectio"], live_commit="old0001"
    )
    await _settle(settings, world)

    assert (await owner_fetch("SELECT status FROM rollbacks"))[0]["status"] == "succeeded"
    assert (await journal(client, project_id))[-2:] == ["rollback.requested", "rollback.succeeded"]
    uses = await owner_fetch("SELECT action FROM connection_events WHERE action = 'rollback'")
    assert len(uses) == 1  # the use of the host's key is traced (FR-024)


async def test_a_rollback_that_never_lands_is_failed_not_claimed(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    _two_commits(world)
    await client.post(f"/api/v1/projects/{project_id}/refresh")
    await client.post(f"/api/v1/projects/{project_id}/rollback")

    await _settle(settings, world, datetime.now(UTC) + ROLLBACK_TIMEOUT + timedelta(minutes=1))

    assert (await owner_fetch("SELECT status FROM rollbacks"))[0]["status"] == "failed"
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project_id, "code": "rollback.failed"} in workshop["verdicts"]


async def test_a_host_that_no_longer_keeps_the_version_says_so(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
) -> None:
    project_id = await lectio(client, identity, world)
    _two_commits(world)
    await client.post(f"/api/v1/projects/{project_id}/refresh")
    world.factory.hosting_adapters["netlify"].rollback_unsupported = True

    refused = await client.post(f"/api/v1/projects/{project_id}/rollback")

    assert refused.status_code == 422
    assert refused.json() == {"error": {"code": "rollback.unsupported"}}
    assert (await journal(client, project_id))[-2:] == ["rollback.requested", "rollback.failed"]


async def test_without_an_earlier_deployment_there_is_nothing_to_go_back_to(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
) -> None:
    project_id = await lectio(client, identity, world)
    stage_nettio(world)
    nettio = (await client.post("/api/v1/projects", json={"repository": NETTIO})).json()

    assert nettio["canRollback"] is False
    refused = await client.post(f"/api/v1/projects/{nettio['id']}/rollback")
    unknown = await client.post("/api/v1/projects/01980000-0000-7000-8000-000000000000/rollback")

    assert refused.json() == {"error": {"code": "rollback.no_previous"}}
    assert unknown.status_code == 404
    assert project_id != nettio["id"]
