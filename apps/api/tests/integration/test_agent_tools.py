"""T014 / T017 — the agent sees and does what the console sees and does, tool by tool, and never
approves a release or runs a rollback (003 US2, US3, FR-006 to FR-012, SC-001, SC-002)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from pono_api.application.rollback_requests import expire_rollback_requests
from pono_api.config import Settings
from pono_api.infrastructure.database.rls import Principal
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World, deployment
from tests.integration.agent_setup import connect, settings  # noqa: F401
from tests.integration.release_setup import (
    HEAD,
    added,
    journal,
    lectio,
    only_release,
    propose,
    read_releases,
)
from tests.integration.workshop_setup import BOB, LECTIO, NETTIO, stage_nettio

pytestmark = [pytest.mark.integration, requires_database]

UNKNOWN = "01980000-0000-7000-8000-000000000000"


def _two_deployments(world: World) -> None:
    netlify = world.factory.hosting_adapters["netlify"]
    netlify.environments["site-lectio"] = replace(
        netlify.environments["site-lectio"],
        deployments=(
            deployment("netlify-2", commit="new0001", age=timedelta(hours=1)),
            deployment("netlify-1", commit="old0001", age=timedelta(days=2)),
        ),
        live_commit="new0001",
    )


async def test_every_read_tool_answers_what_the_console_answers(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await lectio(client, identity, world)
    propose(world, added("src/a.ts", "export const a = 1;"))
    await read_releases(settings, world)
    agent = await connect(client, access="read")

    pairs = [
        (await agent.tool("list_projects"), (await client.get("/api/v1/projects")).json()),
        (
            await agent.tool("list_projects", state="active"),
            (await client.get("/api/v1/projects", params={"state": "active"})).json(),
        ),
        (
            {
                k: v
                for k, v in (await agent.tool("get_project", project_id=project_id)).items()
                if k != "consoleUrl"
            },
            (await client.get(f"/api/v1/projects/{project_id}")).json(),
        ),
        (
            (await agent.tool("list_releases", project_id=project_id))["releases"],
            (await client.get(f"/api/v1/projects/{project_id}/releases")).json(),
        ),
        (
            (await agent.tool("read_journal", project_id=project_id))["entries"],
            (await client.get(f"/api/v1/projects/{project_id}/journal")).json(),
        ),
        (
            (await agent.tool("list_repositories"))["repositories"],
            (await client.get("/api/v1/repositories")).json(),
        ),
    ]

    for tool, console in pairs:
        assert tool == console
    project = await agent.tool("get_project", project_id=project_id)
    assert project["consoleUrl"] == f"http://localhost:3000/workshop/projects/{project_id}"
    assert await agent.tool("get_project", project_id=UNKNOWN) == {"error": "project.not_found"}


async def test_an_agent_acts_like_the_console_and_the_journal_names_it(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await lectio(client, identity, world)
    stage_nettio(world)
    propose(world, added("src/a.ts", "export const a = 1;"))
    world.links.down.add("https://deploy-preview-7--lectio-reads.netlify.app")
    await read_releases(settings, world)
    agent = await connect(client, name="Claude")

    imported = await agent.tool("import_project", repository=NETTIO)
    duplicate = await agent.tool("import_project", repository=NETTIO)
    refreshed = await agent.tool("refresh_project", project_id=project_id)
    protected = await agent.tool("protect_production", project_id=project_id)
    world.links.down.clear()
    release = await only_release(client, project_id)
    evaluated = await agent.tool(
        "evaluate_release", project_id=project_id, release_id=release["id"]
    )

    assert imported["repository"] == NETTIO
    assert duplicate == {"error": "project.already_imported"}
    assert refreshed["id"] == project_id
    assert protected["status"] == "protected"
    assert (evaluated["verdict"], evaluated["headSha"]) == ("awaiting_approval", HEAD)
    events = await owner_fetch(
        "SELECT kind, actor_kind, actor, detail->>'grantedBy' AS granted FROM project_events "
        "WHERE actor_kind = 'agent' AND actor = 'Claude' ORDER BY id"
    )
    assert [(e["kind"], e["actor"], e["granted"]) for e in events] == [
        ("project.imported", "Claude", "alice"),
        ("project.refresh_requested", "Claude", "alice"),
        ("protection.applied", "Claude", "alice"),
        ("release.evaluation_requested", "Claude", "alice"),
    ]
    # The same actions from the console leave the same kinds of entries, under the person.
    await client.post(f"/api/v1/projects/{project_id}/refresh")
    assert (await journal(client, project_id))[-1] == "project.refresh_requested"


async def test_no_tool_approves_a_release_or_runs_a_rollback(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
) -> None:
    await lectio(client, identity, world)
    agent = await connect(client)

    tools = await agent.tools()

    assert set(tools) == {
        "list_projects",
        "get_project",
        "list_releases",
        "read_journal",
        "list_repositories",
        "import_project",
        "refresh_project",
        "evaluate_release",
        "protect_production",
        "request_rollback",
    }
    for name, tool in tools.items():
        annotations = tool["annotations"]
        acts = name in {
            "import_project",
            "refresh_project",
            "evaluate_release",
            "protect_production",
            "request_rollback",
        }
        assert annotations["readOnlyHint"] is (not acts), name  # type: ignore[index]
        assert annotations["destructiveHint"] is acts, name  # type: ignore[index]
    assert not any("approv" in name or "confirm" in name for name in tools)


async def test_an_agent_only_asks_for_a_rollback_and_a_person_decides(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await lectio(client, identity, world)
    _two_deployments(world)
    await client.post(f"/api/v1/projects/{project_id}/refresh")
    agent = await connect(client, name="Codex")

    asked = await agent.tool("request_rollback", project_id=project_id)
    twice = await agent.tool("request_rollback", project_id=project_id)

    assert asked["clientName"] == "Codex"
    assert twice == {"error": "rollback.request_pending"}
    assert world.factory.hosting_adapters["netlify"].rolled_back == []  # production untouched
    detail = (await client.get(f"/api/v1/projects/{project_id}")).json()
    assert detail["rollbackRequest"]["clientName"] == "Codex"
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project_id, "code": "rollback.requested"} in workshop["verdicts"]

    base = f"/api/v1/projects/{project_id}/rollback-requests/{asked['id']}"
    confirmed = await client.post(f"{base}/confirm")
    closed = await client.post(f"{base}/dismiss")

    assert confirmed.status_code == 200
    assert confirmed.json()["rollbackRequest"] is None
    assert world.factory.hosting_adapters["netlify"].rolled_back == [("site-lectio", "netlify-1")]
    assert closed.json() == {"error": {"code": "rollback.request_closed"}}
    kinds = await journal(client, project_id)
    assert "rollback.requested_by_agent" in kinds
    assert kinds[-2:] == ["rollback.requested", "rollback.request_confirmed"]


async def test_a_rollback_request_can_be_dismissed_or_expires(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await lectio(client, identity, world)
    _two_deployments(world)
    await client.post(f"/api/v1/projects/{project_id}/refresh")
    agent = await connect(client)

    first = await agent.tool("request_rollback", project_id=project_id)
    dismissed = await client.post(
        f"/api/v1/projects/{project_id}/rollback-requests/{first['id']}/dismiss"
    )
    assert dismissed.json()["rollbackRequest"] is None
    await agent.tool("request_rollback", project_id=project_id)

    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    try:
        organization = (await owner_fetch("SELECT id FROM organizations"))[0]["id"]
        expired = await expire_rollback_requests(
            create_session_factory(engine),
            Principal.for_organization(organization),
            datetime.now(UTC) + timedelta(hours=25),
        )
    finally:
        await engine.dispose()

    assert expired == 1
    assert world.factory.hosting_adapters["netlify"].rolled_back == []
    assert (await journal(client, project_id))[-1] == "rollback.request_expired"


async def test_another_organization_stays_out_of_reach(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
) -> None:
    project_id = await lectio(client, identity, world)
    await sign_in_as(client, identity, BOB)
    bobs_agent = await connect(client, name="Bob's agent")

    assert await bobs_agent.tool("get_project", project_id=project_id) == {
        "error": "project.not_found"
    }
    assert await bobs_agent.tool("request_rollback", project_id=project_id) == {
        "error": "project.not_found"
    }
    assert (await bobs_agent.tool("list_projects"))["projects"] == []
    assert LECTIO not in str(await bobs_agent.tool("list_projects"))
