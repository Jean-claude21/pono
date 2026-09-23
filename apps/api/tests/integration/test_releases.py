"""T013 / T023 — a dangerous change is refused and blocked; nothing ships without a person's
approval of its exact version (002 US1, US2, FR-001 to FR-012)."""

import httpx
import pytest

from pono_api.application.ports import PreviewState
from pono_api.config import Settings
from tests.conftest import FakeIdentity, requires_database, sign_in_as
from tests.fakes import World
from tests.integration.release_setup import (
    HEAD,
    NEXT_HEAD,
    added,
    change,
    journal,
    lectio,
    only_release,
    propose,
    read_releases,
)
from tests.integration.workshop_setup import BOB, LECTIO

pytestmark = [pytest.mark.integration, requires_database]

DROP = "drizzle/0003_drop_notes.sql"
ADD = "drizzle/0003_add_tags.sql"


async def test_a_destructive_migration_is_refused_and_the_merge_stays_blocked(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    propose(
        world,
        added(
            DROP, "ALTER TABLE books ADD COLUMN tags text;", "ALTER TABLE notes DROP COLUMN body;"
        ),
        added("src/notes.ts", "export const notes = [];"),
        migrations={
            DROP: "ALTER TABLE books ADD COLUMN tags text;\nALTER TABLE notes DROP COLUMN body;"
        },
    )

    await read_releases(settings, world)

    release = await only_release(client, project_id)
    assert (release["verdict"], release["headSha"], release["changeNumber"]) == ("refused", HEAD, 7)
    guards = {g["guard"]: g for g in release["guards"]}  # type: ignore[attr-defined]
    assert guards["migrations"]["status"] == "failed"
    assert guards["migrations"]["findings"][0] == {
        "code": "migrations.destructive",
        "file": DROP,
        "line": 2,
        "operation": "drop_column",
        "url": None,
    }
    assert (guards["secrets"]["status"], guards["preview"]["status"]) == ("passed", "passed")
    assert world.code_host.check_of(HEAD) == "failure"
    assert await journal(client, project_id) == [
        "protection.missing",
        "release.opened",
        "release.evaluated",
        "release.refused",
    ]
    refused = await client.post(
        f"/api/v1/projects/{project_id}/releases/{release['id']}/approval", json={"headSha": HEAD}
    )
    assert refused.json() == {"error": {"code": "release.not_ready"}}
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project_id, "code": "release.refused"} in workshop["verdicts"]


async def test_a_clean_change_waits_for_a_person_then_only_that_version_ships(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    propose(
        world,
        added(ADD, "ALTER TABLE books ADD COLUMN tags text;"),
        migrations={ADD: "ALTER TABLE books ADD COLUMN tags text;"},
    )

    await read_releases(settings, world)
    await read_releases(settings, world)  # a second tick publishes nothing new

    release = await only_release(client, project_id)
    assert release["verdict"] == "awaiting_approval"
    assert world.code_host.checks == [(LECTIO, HEAD, "pending")]
    approval = f"/api/v1/projects/{project_id}/releases/{release['id']}/approval"

    stale = await client.post(approval, json={"headSha": NEXT_HEAD})
    approved = await client.post(approval, json={"headSha": HEAD})

    assert stale.json() == {"error": {"code": "release.version_changed"}}
    assert approved.status_code == 200
    body = approved.json()
    assert (body["verdict"], body["approvedBy"]) == ("approved", "alice")
    assert world.code_host.check_of(HEAD) == "success"

    # A new commit: the approval no longer covers it, the check is pending again.
    propose(world, added("src/notes.ts", "export const more = 1;"), head=NEXT_HEAD)
    await read_releases(settings, world)

    release = await only_release(client, project_id)
    assert (release["verdict"], release["headSha"], release["approvedBy"]) == (
        "awaiting_approval",
        NEXT_HEAD,
        None,
    )
    assert world.code_host.check_of(NEXT_HEAD) == "pending"
    assert await journal(client, project_id) == [
        "protection.missing",
        "release.opened",
        "release.evaluated",
        "release.awaiting_approval",
        "release.approved",
        "release.approval_invalidated",
        "release.evaluated",
        "release.awaiting_approval",
    ]


async def test_a_secret_is_refused_without_its_value_ever_being_kept(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    token = "ghp_" + "S3cr3tV4lu3" * 4
    propose(world, added("src/config.ts", f'export const token = "{token}";'))

    await read_releases(settings, world)

    release = await only_release(client, project_id)
    assert release["verdict"] == "refused"
    everything = str(release) + str(
        (await client.get(f"/api/v1/projects/{project_id}/journal")).json()
    )
    assert token not in everything


async def test_a_missing_preview_or_an_unreachable_host_never_lets_it_through(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    propose(world, added("src/a.ts", "export const a = 1;"), preview=PreviewState("building"))
    await read_releases(settings, world)
    assert (await only_release(client, project_id))["verdict"] == "evaluating"
    assert world.code_host.check_of(HEAD) == "pending"

    world.factory.hosting_adapters["netlify"].unavailable = True
    await read_releases(settings, world)
    assert (await only_release(client, project_id))["verdict"] == "evaluating"

    world.factory.hosting_adapters["netlify"].unavailable = False
    world.factory.hosting_adapters["netlify"].previews[(7, HEAD)] = PreviewState("failed")
    await read_releases(settings, world)
    assert (await only_release(client, project_id))["verdict"] == "refused"
    assert world.code_host.check_of(HEAD) == "failure"


async def test_a_merge_without_approval_is_said_aloud(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    propose(world, added("src/a.ts", "export const a = 1;"))
    await read_releases(settings, world)

    world.code_host.changes[LECTIO] = []
    world.code_host.finished[(LECTIO, 7)] = change(7, HEAD, state="merged")
    await read_releases(settings, world)

    release = await only_release(client, project_id)
    assert release["state"] == "merged"
    assert (await journal(client, project_id))[-1] == "release.merged_without_approval"
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project_id, "code": "release.merged_without_approval"} in workshop[
        "verdicts"
    ]


async def test_an_approved_merge_and_a_closed_change_are_recorded(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    propose(world, added("src/a.ts", "export const a = 1;"))
    await read_releases(settings, world)
    release = await only_release(client, project_id)
    await client.post(
        f"/api/v1/projects/{project_id}/releases/{release['id']}/approval", json={"headSha": HEAD}
    )
    world.code_host.changes[LECTIO] = []
    world.code_host.finished[(LECTIO, 7)] = change(7, HEAD, state="merged")
    await read_releases(settings, world)

    assert (await journal(client, project_id))[-1] == "release.merged"
    workshop = (await client.get("/api/v1/projects")).json()
    assert all(v["code"] != "release.merged_without_approval" for v in workshop["verdicts"])


async def test_an_approval_needs_the_code_host_and_records_nothing_without_it(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    propose(world, added("src/a.ts", "export const a = 1;"))
    await read_releases(settings, world)
    release = await only_release(client, project_id)
    world.code_host.checks_unavailable = True

    failed = await client.post(
        f"/api/v1/projects/{project_id}/releases/{release['id']}/approval", json={"headSha": HEAD}
    )

    assert failed.status_code == 503
    assert failed.json() == {"error": {"code": "provider.unavailable"}}
    assert (await only_release(client, project_id))["verdict"] == "awaiting_approval"
    assert "release.approved" not in await journal(client, project_id)


async def test_another_organization_can_neither_see_nor_approve(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    propose(world, added("src/a.ts", "export const a = 1;"))
    await read_releases(settings, world)
    release = await only_release(client, project_id)

    await sign_in_as(client, identity, BOB)
    base = f"/api/v1/projects/{project_id}"
    seen = await client.get(f"{base}/releases")
    approved = await client.post(
        f"{base}/releases/{release['id']}/approval", json={"headSha": HEAD}
    )
    logged = await client.get(f"{base}/journal")

    assert [r.status_code for r in (seen, approved, logged)] == [404, 404, 404]


async def test_evaluating_again_on_request(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await lectio(client, identity, world)
    url = "https://deploy-preview-7--lectio-reads.netlify.app"
    world.links.down.add(url)
    propose(world, added("src/a.ts", "export const a = 1;"))
    await read_releases(settings, world)
    release = await only_release(client, project_id)
    assert release["verdict"] == "refused"

    world.links.down.clear()
    queued = await client.post(f"/api/v1/projects/{project_id}/releases/{release['id']}/evaluation")

    assert queued.status_code == 202
    assert (await only_release(client, project_id))["verdict"] == "awaiting_approval"
